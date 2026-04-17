import { SqliteStore } from '../storage/sqlite-store.js';
import { SwitchDaemon } from './switch-daemon.js';

export class AlephEngine {
  constructor(options = {}) {
    this.store = options.store ?? new SqliteStore({ rootDir: options.rootDir });
    this.switchDaemon = options.switchDaemon ?? new SwitchDaemon();
    this.now = options.now ?? (() => Date.now());
    this.personaHandlers = new Map();
  }

  registerPersona(profile, handler) {
    this.store.savePersonaProfile(profile);
    this.personaHandlers.set(profile.id, handler);
  }

  listPersonas() {
    return this.store.listPersonaProfiles();
  }

  bootstrap(input = {}) {
    let thread = this.store.getLatestRealityThread();
    if (!thread) {
      thread = this.store.createRealityThread({
        title: input.title ?? 'Aleph MVP Thread',
        summary:
          input.summary ??
          'A single continuous reality is active. Different personas may take foreground, but reality keeps moving.',
        activeScene: input.activeScene ?? 'A user has opened a new conversation with Aleph.',
        openLoops: input.openLoops ?? [],
      });
    }

    if (!this.store.getForegroundControl()) {
      const initialPersonaId = input.initialPersonaId ?? this.listPersonas()[0]?.id;
      if (!initialPersonaId) {
        throw new Error('Cannot bootstrap Aleph without at least one registered persona.');
      }
      const session = this.store.createSession({
        personaId: initialPersonaId,
        status: 'active',
        handoffSummary: 'Initial foreground session.',
      });
      this.store.setForegroundControl({
        threadId: thread.id,
        personaId: initialPersonaId,
        sessionId: session.id,
        reason: 'bootstrap',
      });
    }

    return this.inspectState();
  }

  processUserTurn(userInput, options = {}) {
    const control = this.store.getForegroundControl();
    if (!control) {
      throw new Error('Aleph is not bootstrapped.');
    }

    if (options.requestedPersonaId && options.requestedPersonaId !== control.personaId) {
      this._switchForeground({
        reason: `user explicitly summoned ${options.requestedPersonaId}`,
        targetPersonaId: options.requestedPersonaId,
        trigger: 'user',
        userInput,
      });
    }

    const current = this.store.getForegroundControl();
    const threadId = current.threadId;

    const userEvent = this.store.appendRealityEvent({
      threadId,
      type: 'user.turn',
      source: 'user',
      summary: userInput,
      payload: {
        requestedPersonaId: options.requestedPersonaId ?? null,
      },
    });

    return this._runPersonaTurn({
      personaId: this.store.getForegroundControl().personaId,
      userInput,
      sourceEventId: userEvent.id,
      switchBudget: 1,
    });
  }

  _runPersonaTurn(context) {
    const persona = this.store.getPersonaProfile(context.personaId);
    if (!persona) {
      throw new Error(`Persona '${context.personaId}' is not registered.`);
    }

    const handler = this.personaHandlers.get(persona.id);
    if (!handler) {
      throw new Error(`Persona '${persona.id}' has no registered handler.`);
    }

    const reality = this.store.getRealityProjection(this.store.getForegroundControl().threadId);
    const input = {
      userInput: context.userInput,
      sourceEventId: context.sourceEventId,
      currentPersona: persona,
      reality,
      privateMemoryContext: this.store.listMemories({
        layer: 'private',
        personaId: persona.id,
        limit: 6,
      }),
      sharedMemoryContext: this.store.listMemories({
        layer: 'shared',
        domains: persona.sharedDomains,
        limit: 8,
      }),
      latestHandoff: this.store.listSwitchLogs(1)[0] ?? null,
    };

    const output = handler(input);
    this._persistPersonaOutput(persona, output, context.sourceEventId);

    if (output.switchRequest && context.switchBudget > 0) {
      const decision = this._switchForeground({
        reason: output.switchRequest.reason,
        targetPersonaId: output.switchRequest.targetPersonaId,
        trigger: 'daemon',
        userInput: context.userInput,
      });

      if (decision.approved && output.switchRequest.replayTurn !== false) {
        const next = this._runPersonaTurn({
          personaId: decision.targetPersonaId,
          userInput: context.userInput,
          sourceEventId: context.sourceEventId,
          switchBudget: 0,
        });
        return {
          ...next,
          switchDecision: decision,
          priorPersonaId: persona.id,
        };
      }

      return {
        activePersonaId: persona.id,
        activePersonaName: persona.name,
        reply: output.reply,
        switchDecision: decision,
        reality: this.store.getRealityProjection(reality.thread.id),
      };
    }

    return {
      activePersonaId: persona.id,
      activePersonaName: persona.name,
      reply: output.reply,
      reality: this.store.getRealityProjection(reality.thread.id),
      switchDecision: null,
    };
  }

  _persistPersonaOutput(persona, output, sourceEventId) {
    for (const memory of output.privateMemories ?? []) {
      this.store.saveMemory({
        layer: 'private',
        personaId: persona.id,
        kind: memory.kind,
        content: memory.content,
        metadata: memory.metadata ?? {},
      });
    }

    for (const memory of output.sharedMemories ?? []) {
      if (!persona.sharedDomains.includes(memory.domain)) {
        continue;
      }
      this.store.saveMemory({
        layer: 'shared',
        domain: memory.domain,
        kind: memory.kind,
        content: memory.content,
        metadata: memory.metadata ?? {},
      });
    }

    for (const note of output.realityUpdates?.realityNotes ?? []) {
      this.store.saveMemory({
        layer: 'reality-note',
        kind: note.kind ?? 'note',
        content: note.content,
        metadata: note.metadata ?? {},
      });
    }

    const projection = this.store.getRealityProjection(this.store.getForegroundControl().threadId);
    const openLoops = [...projection.thread.openLoops];

    for (const loop of output.realityUpdates?.openLoopsToAdd ?? []) {
      if (!openLoops.includes(loop)) openLoops.push(loop);
    }

    for (const loop of output.realityUpdates?.openLoopsToResolve ?? []) {
      const index = openLoops.indexOf(loop);
      if (index >= 0) openLoops.splice(index, 1);
    }

    if (
      (output.realityUpdates?.openLoopsToAdd?.length ?? 0) > 0 ||
      (output.realityUpdates?.openLoopsToResolve?.length ?? 0) > 0
    ) {
      this.store.updateRealityThread(projection.thread.id, { openLoops });
    }

    for (const change of output.realityUpdates?.consequences ?? []) {
      if (change.op === 'resolve') {
        this.store.resolveConsequence({
          threadId: projection.thread.id,
          kind: change.kind,
          id: change.id,
        });
      } else {
        this.store.upsertConsequence({
          threadId: projection.thread.id,
          kind: change.kind,
          sourceEventId,
          summary: change.summary,
          weight: change.weight,
          scope: change.scope,
          handoffHint: change.handoffHint,
          metadata: change.metadata ?? {},
        });
      }
    }

    this.store.appendRealityEvent({
      threadId: projection.thread.id,
      type: 'persona.turn',
      source: persona.id,
      summary: output.reply,
      payload: {
        reply: output.reply,
        requestedSwitch: output.switchRequest ?? null,
      },
    });

    const nextProjection = this.store.getRealityProjection(projection.thread.id);
    const latestConsequence = nextProjection.consequences[0]?.summary;
    const latestOpenLoop = nextProjection.thread.openLoops[0];
    const summary = latestConsequence
      ? `Foreground reality still carries: ${latestConsequence}`
      : latestOpenLoop
        ? `Foreground reality still carries the loop: ${latestOpenLoop}`
        : 'Foreground reality is stable for now.';

    this.store.updateRealityThread(projection.thread.id, {
      summary,
      activeScene: `Foreground persona ${persona.name} just responded to the user.`,
    });
  }

  _switchForeground(input) {
    const control = this.store.getForegroundControl();
    const reality = this.store.getRealityProjection(control.threadId);
    const currentPersona = this.store.getPersonaProfile(control.personaId);
    const personas = this.store.listPersonaProfiles();

    const decision = this.switchDaemon.decide({
      reason: input.reason,
      targetPersonaId: input.targetPersonaId,
      currentPersona,
      personas,
      reality,
      userInput: input.userInput,
    });

    if (!decision.approved) {
      return decision;
    }

    const session = this.store.createSession({
      personaId: decision.targetPersonaId,
      status: 'active',
      handoffSummary: decision.handoffSummary,
    });

    this.store.setForegroundControl({
      threadId: control.threadId,
      personaId: decision.targetPersonaId,
      sessionId: session.id,
      reason: input.reason,
    });

    this.store.recordSwitch({
      fromPersonaId: currentPersona?.id ?? null,
      toPersonaId: decision.targetPersonaId,
      reason: input.reason,
      explanation: decision.explanation,
      handoffSummary: decision.handoffSummary,
      trigger: input.trigger ?? 'daemon',
    });

    return decision;
  }

  inspectState() {
    const control = this.store.getForegroundControl();
    if (!control) {
      return {
        personas: this.store.listPersonaProfiles(),
        foreground: null,
        reality: null,
        switches: [],
      };
    }

    return {
      personas: this.store.listPersonaProfiles(),
      foreground: control,
      reality: this.store.getRealityProjection(control.threadId),
      switches: this.store.listSwitchLogs(5),
    };
  }
}

