import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createEngine } from '../src/demo/helpers.js';

function withEngine(run) {
  const rootDir = mkdtempSync(join(tmpdir(), 'aleph-test-'));
  const engine = createEngine(rootDir);

  try {
    run(engine);
  } finally {
    engine.store.close();
    rmSync(rootDir, { recursive: true, force: true });
  }
}

test('continuous reality survives persona switch', () => {
  withEngine((engine) => {
    engine.processUserTurn('我答应合作方今晚之前发过去。');
    const switched = engine.processUserTurn('你来拍板并接管。');

    assert.equal(switched.activePersonaId, 'sol');
    assert.equal(switched.switchDecision?.approved, true);
    assert.match(switched.reply, /inherit/i);

    const state = engine.inspectState();
    assert.equal(state.foreground.personaId, 'sol');
    assert.ok(
      state.reality.consequences.some((item) => item.kind === 'pending_commitment'),
    );
  });
});

test('private memory stays private while shared memory remains visible', () => {
  withEngine((engine) => {
    engine.processUserTurn('我答应合作方今晚之前发过去。');
    engine.processUserTurn('你来拍板并接管。');

    const irisPrivate = engine.store.listMemories({
      layer: 'private',
      personaId: 'iris',
      limit: 20,
    });
    const solPrivate = engine.store.listMemories({
      layer: 'private',
      personaId: 'sol',
      limit: 20,
    });
    const solShared = engine.store.listMemories({
      layer: 'shared',
      domains: ['commitments', 'social'],
      limit: 20,
    });

    assert.ok(irisPrivate.some((item) => item.content.includes('Iris noted')));
    assert.ok(solPrivate.some((item) => item.content.includes('Sol evaluated')));
    assert.ok(solShared.some((item) => item.domain === 'commitments'));
    assert.ok(!solPrivate.some((item) => item.content.includes('Iris noted')));
  });
});

test('switches are explainable and logged', () => {
  withEngine((engine) => {
    const result = engine.processUserTurn('你来拍板并接管吧，我们得推进。');

    assert.equal(result.switchDecision?.approved, true);
    assert.match(result.switchDecision.explanation, /takes foreground/i);
    assert.match(result.switchDecision.handoffSummary, /Incoming persona/i);

    const latestSwitch = engine.inspectState().switches[0];
    assert.equal(latestSwitch.toPersonaId, 'sol');
    assert.match(latestSwitch.reason, /authority/i);
  });
});

test('foreground control stays singular after multiple turns', () => {
  withEngine((engine) => {
    engine.processUserTurn('我答应合作方今晚之前发过去。');
    engine.processUserTurn('你来拍板并接管。');
    engine.processUserTurn('我刚刚把话说重了，关系有点僵。');

    const foreground = engine.store.getForegroundControl();
    assert.ok(foreground);
    assert.ok(['sol', 'mire'].includes(foreground.personaId));

    const allForegroundRows = engine.store.db
      .prepare('SELECT COUNT(*) AS count FROM foreground_control')
      .get();
    assert.equal(allForegroundRows.count, 1);
  });
});
