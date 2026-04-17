export class SwitchDaemon {
  constructor(options = {}) {
    this.now = options.now ?? (() => Date.now());
  }

  decide(context) {
    const targetPersona =
      context.targetPersonaId
        ? context.personas.find((persona) => persona.id === context.targetPersonaId)
        : this._choosePersona(context);

    if (!targetPersona) {
      return {
        approved: false,
        explanation: 'No suitable target persona is available for handoff.',
        handoffSummary: '',
      };
    }

    if (context.currentPersona && targetPersona.id === context.currentPersona.id) {
      return {
        approved: false,
        explanation: `${targetPersona.name} already holds foreground control.`,
        handoffSummary: '',
      };
    }

    const handoffSummary = this._buildHandoffSummary(context, targetPersona);
    return {
      approved: true,
      targetPersonaId: targetPersona.id,
      explanation: `${targetPersona.name} takes foreground because ${this._explainReason(context.reason)}.`,
      handoffSummary,
      decidedAt: this.now(),
    };
  }

  _choosePersona(context) {
    const reason = (context.reason ?? '').toLowerCase();
    const candidates = context.personas.filter(
      (persona) => !context.currentPersona || persona.id !== context.currentPersona.id,
    );

    if (reason.includes('authority') || reason.includes('permission') || reason.includes('decide')) {
      return candidates.find((persona) => persona.permissions.includes('authority'));
    }

    if (reason.includes('memory') || reason.includes('history') || reason.includes('recall')) {
      return candidates.find((persona) => persona.specialties.includes('memory'));
    }

    if (reason.includes('relationship') || reason.includes('social') || reason.includes('emotional')) {
      return candidates.find((persona) => persona.specialties.includes('social'));
    }

    return candidates[0] ?? null;
  }

  _explainReason(reason) {
    if (!reason) return 'the current situation called for a different perspective';
    return reason;
  }

  _buildHandoffSummary(context, targetPersona) {
    const consequenceSummary = context.reality.consequences
      .slice(0, 3)
      .map((item) => item.handoffHint || item.summary)
      .join(' | ');
    const openLoops = context.reality.thread.openLoops.slice(0, 3).join(' | ');

    return [
      `Incoming persona: ${targetPersona.name}`,
      `Scene: ${context.reality.thread.activeScene}`,
      `Reality summary: ${context.reality.thread.summary}`,
      consequenceSummary ? `Inherited consequences: ${consequenceSummary}` : null,
      openLoops ? `Open loops: ${openLoops}` : null,
      context.userInput ? `User turn to address: ${context.userInput}` : null,
    ]
      .filter(Boolean)
      .join('\n');
  }
}

