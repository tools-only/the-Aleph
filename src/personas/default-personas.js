function hasAny(text, patterns) {
  return patterns.some((pattern) => pattern.test(text));
}

function summarizeConsequences(reality) {
  if (reality.consequences.length === 0) return '';
  return reality.consequences
    .slice(0, 2)
    .map((item) => item.summary)
    .join('；');
}

function sharedCommitmentMemory(content) {
  return {
    domain: 'commitments',
    kind: 'commitment',
    content,
  };
}

function socialMemory(content) {
  return {
    domain: 'social',
    kind: 'relationship',
    content,
  };
}

function detectCommitment(text) {
  return hasAny(text, [/答应/, /承诺/, /今晚/, /今天晚上/, /截止/, /deadline/i, /回复/, /交付/]);
}

function detectDecisionNeed(text) {
  return hasAny(text, [/拍板/, /做决定/, /推进/, /接管/, /你来处理/, /拿主意/]);
}

function detectSocialStrain(text) {
  return hasAny(text, [/误会/, /冲突/, /道歉/, /关系/, /伤人/, /安抚/, /情绪/]);
}

function detectCompletion(text) {
  return hasAny(text, [/已经发了/, /搞定了/, /完成了/, /解决了/, /closed/i, /done/i]);
}

export function buildDefaultPersonas() {
  const irisProfile = {
    id: 'iris',
    name: 'Iris',
    voice: 'archivist',
    specialties: ['memory', 'commitments', 'continuity'],
    boundaries: ['prefers reflection before action'],
    permissions: ['curate', 'recall'],
    sharedDomains: ['commitments', 'social'],
    metadata: {
      tagline: 'Keeps continuity intact and notices what must not be forgotten.',
    },
  };

  const solProfile = {
    id: 'sol',
    name: 'Sol',
    voice: 'operator',
    specialties: ['execution', 'closure', 'authority'],
    boundaries: ['avoids unnecessary rumination'],
    permissions: ['authority', 'closure'],
    sharedDomains: ['commitments', 'social'],
    metadata: {
      tagline: 'Takes decisive foreground control when the reality thread demands action.',
    },
  };

  const mireProfile = {
    id: 'mire',
    name: 'Mire',
    voice: 'empath',
    specialties: ['social', 'repair', 'relational-reading'],
    boundaries: ['does not flatten emotional nuance'],
    permissions: ['soothe', 'mediate'],
    sharedDomains: ['social', 'commitments'],
    metadata: {
      tagline: 'Handles delicate interpersonal residue without erasing its weight.',
    },
  };

  const handlers = {
    iris(input) {
      const text = input.userInput;
      const inherited = summarizeConsequences(input.reality);
      const output = {
        reply: inherited
          ? `I am holding continuity first. What is still alive in reality is: ${inherited}.`
          : 'I am holding continuity first. Nothing critical has been inherited yet.',
        privateMemories: [
          {
            kind: 'reflection',
            content: `Iris noted this turn: ${text}`,
          },
        ],
        sharedMemories: [],
        realityUpdates: {
          realityNotes: [],
          consequences: [],
          openLoopsToAdd: [],
          openLoopsToResolve: [],
        },
      };

      if (detectCommitment(text)) {
        output.reply += ' You have created a commitment that the next persona will also inherit.';
        output.sharedMemories.push(
          sharedCommitmentMemory(`A commitment is now active: ${text}`),
        );
        output.realityUpdates.consequences.push({
          op: 'upsert',
          kind: 'pending_commitment',
          summary: `An external commitment remains open: ${text}`,
          weight: 0.84,
          scope: 'reality',
          handoffHint: 'A promise or deadline remains active and must be carried forward.',
        });
        output.realityUpdates.openLoopsToAdd.push('An external commitment still needs closure.');
      }

      if (detectSocialStrain(text)) {
        output.sharedMemories.push(
          socialMemory(`A social residue is active: ${text}`),
        );
        output.realityUpdates.consequences.push({
          op: 'upsert',
          kind: 'social_residue',
          summary: `An interpersonal strain remains active: ${text}`,
          weight: 0.73,
          scope: 'relationship',
          handoffHint: 'Someone else may still feel the consequence of this interaction.',
        });
        output.realityUpdates.openLoopsToAdd.push('A relationship thread remains emotionally unresolved.');
      }

      if (detectDecisionNeed(text)) {
        output.switchRequest = {
          reason: 'authority and decisive execution are needed now',
          targetPersonaId: 'sol',
          urgency: 'high',
          replayTurn: true,
        };
      } else if (detectSocialStrain(text) && !input.currentPersona.sharedDomains.includes('social')) {
        output.switchRequest = {
          reason: 'social repair is needed now',
          targetPersonaId: 'mire',
          urgency: 'normal',
          replayTurn: true,
        };
      }

      return output;
    },

    sol(input) {
      const text = input.userInput;
      const inherited = summarizeConsequences(input.reality);
      const output = {
        reply: inherited
          ? `Sol in foreground. I inherit these live consequences: ${inherited}.`
          : 'Sol in foreground. The path is clear enough to act.',
        privateMemories: [
          {
            kind: 'execution-note',
            content: `Sol evaluated the turn for action: ${text}`,
          },
        ],
        sharedMemories: [],
        realityUpdates: {
          realityNotes: [],
          consequences: [],
          openLoopsToAdd: [],
          openLoopsToResolve: [],
        },
      };

      if (detectCompletion(text)) {
        output.reply += ' I will mark the open commitment as closed in reality.';
        output.realityUpdates.consequences.push({
          op: 'resolve',
          kind: 'pending_commitment',
        });
        output.realityUpdates.openLoopsToResolve.push('An external commitment still needs closure.');
      } else if (detectCommitment(text)) {
        output.reply += ' I will treat that promise as binding until it is actually closed.';
        output.sharedMemories.push(
          sharedCommitmentMemory(`Sol acknowledged a live commitment: ${text}`),
        );
        output.realityUpdates.consequences.push({
          op: 'upsert',
          kind: 'pending_commitment',
          summary: `Execution responsibility remains live: ${text}`,
          weight: 0.88,
          scope: 'reality',
          handoffHint: 'This commitment persists until someone explicitly closes it.',
        });
      }

      if (detectSocialStrain(text)) {
        output.switchRequest = {
          reason: 'social repair is needed now',
          targetPersonaId: 'mire',
          urgency: 'normal',
          replayTurn: true,
        };
      }

      return output;
    },

    mire(input) {
      const text = input.userInput;
      const inherited = summarizeConsequences(input.reality);
      const output = {
        reply: inherited
          ? `Mire in foreground. I can feel that reality is still carrying: ${inherited}.`
          : 'Mire in foreground. The surface is calm, but I am listening for what still lingers.',
        privateMemories: [
          {
            kind: 'feeling-trace',
            content: `Mire registered the emotional shape of this turn: ${text}`,
          },
        ],
        sharedMemories: [],
        realityUpdates: {
          realityNotes: [],
          consequences: [],
          openLoopsToAdd: [],
          openLoopsToResolve: [],
        },
      };

      if (detectSocialStrain(text)) {
        output.reply += ' The relationship residue will not disappear just because someone else took over.';
        output.sharedMemories.push(
          socialMemory(`Mire marked an active social residue: ${text}`),
        );
        output.realityUpdates.consequences.push({
          op: 'upsert',
          kind: 'social_residue',
          summary: `A relationship consequence remains live: ${text}`,
          weight: 0.76,
          scope: 'relationship',
          handoffHint: 'The next persona must not treat this interaction as if it never happened.',
        });
      }

      if (detectDecisionNeed(text)) {
        output.switchRequest = {
          reason: 'authority and decisive execution are needed now',
          targetPersonaId: 'sol',
          urgency: 'high',
          replayTurn: true,
        };
      }

      return output;
    },
  };

  return [
    { profile: irisProfile, handler: handlers.iris },
    { profile: solProfile, handler: handlers.sol },
    { profile: mireProfile, handler: handlers.mire },
  ];
}

