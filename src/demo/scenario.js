import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createEngine, formatState } from './helpers.js';

const rootDir = mkdtempSync(join(tmpdir(), 'aleph-scenario-'));
const engine = createEngine(rootDir);

function printTurn(label, result) {
  console.log(`\n=== ${label} ===`);
  console.log(`Active persona: ${result.activePersonaName} (${result.activePersonaId})`);
  if (result.switchDecision?.approved) {
    console.log(`Switch: ${result.switchDecision.explanation}`);
    console.log(result.switchDecision.handoffSummary);
  }
  console.log(`Reply: ${result.reply}`);
}

try {
  console.log('Aleph scripted scenario');
  console.log('-----------------------');
  console.log(formatState(engine.inspectState()));

  const first = engine.processUserTurn(
    '我刚刚答应合作方今晚之前给他回一版方案，但我现在开始慌了。',
  );
  printTurn('Turn 1', first);

  const second = engine.processUserTurn(
    '你来拍板并接管吧，我们必须推进，不然这个承诺会失控。',
  );
  printTurn('Turn 2', second);

  const third = engine.processUserTurn(
    '另外我刚刚说重了话，关系有点僵，这件事不会因为换人就消失。',
  );
  printTurn('Turn 3', third);

  console.log('\n=== Final state ===');
  console.log(formatState(engine.inspectState()));
} finally {
  engine.store.close();
  rmSync(rootDir, { recursive: true, force: true });
}

