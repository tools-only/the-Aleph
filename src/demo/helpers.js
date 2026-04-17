import { mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { AlephEngine } from '../core/aleph-engine.js';
import { SqliteStore } from '../storage/sqlite-store.js';
import { buildDefaultPersonas } from '../personas/default-personas.js';

export function createEngine(rootDir) {
  mkdirSync(join(rootDir, 'data'), { recursive: true });
  const store = new SqliteStore({ rootDir });
  const engine = new AlephEngine({ rootDir, store });

  for (const { profile, handler } of buildDefaultPersonas()) {
    engine.registerPersona(profile, handler);
  }

  engine.bootstrap({
    initialPersonaId: 'iris',
    title: 'Aleph Demo Thread',
    summary: 'A single reality is active. Personas may change, but consequences remain.',
    activeScene: 'The user has entered a fragile situation that may require a handoff.',
  });

  return engine;
}

export function formatState(state) {
  const currentPersona = state.personas.find(
    (persona) => persona.id === state.foreground?.personaId,
  );

  return [
    `Foreground: ${currentPersona?.name ?? 'none'} (${state.foreground?.personaId ?? 'n/a'})`,
    `Scene: ${state.reality?.thread.activeScene ?? 'n/a'}`,
    `Summary: ${state.reality?.thread.summary ?? 'n/a'}`,
    `Open loops: ${state.reality?.thread.openLoops.join(' | ') || 'none'}`,
    `Consequences: ${
      state.reality?.consequences.map((item) => item.summary).join(' | ') || 'none'
    }`,
    `Latest switch: ${
      state.switches[0]
        ? `${state.switches[0].fromPersonaId ?? 'none'} -> ${state.switches[0].toPersonaId} (${state.switches[0].reason})`
        : 'none'
    }`,
  ].join('\n');
}

