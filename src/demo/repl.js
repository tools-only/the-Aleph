import readline from 'node:readline/promises';
import { stdin as input, stdout as output } from 'node:process';
import { createEngine, formatState } from './helpers.js';

const engine = createEngine(process.cwd());
const rl = readline.createInterface({ input, output });

console.log('Aleph REPL');
console.log('Type /personas, /switch <id>, /state, or /quit');
console.log(formatState(engine.inspectState()));

try {
  while (true) {
    const line = (await rl.question('\nYou> ')).trim();
    if (!line) continue;

    if (line === '/quit' || line === '/exit') {
      break;
    }

    if (line === '/personas') {
      for (const persona of engine.listPersonas()) {
        console.log(
          `- ${persona.id}: ${persona.name} | specialties=${persona.specialties.join(', ')} | shared=${persona.sharedDomains.join(', ')}`,
        );
      }
      continue;
    }

    if (line === '/state') {
      console.log(formatState(engine.inspectState()));
      continue;
    }

    if (line.startsWith('/switch ')) {
      const targetPersonaId = line.slice('/switch '.length).trim();
      const result = engine.processUserTurn(
        `Foreground handoff requested to ${targetPersonaId}.`,
        { requestedPersonaId: targetPersonaId },
      );
      console.log(`${result.activePersonaName}> ${result.reply}`);
      if (result.switchDecision?.approved) {
        console.log(result.switchDecision.explanation);
      }
      continue;
    }

    const result = engine.processUserTurn(line);
    console.log(`${result.activePersonaName}> ${result.reply}`);
    if (result.switchDecision?.approved) {
      console.log(result.switchDecision.explanation);
    }
  }
} finally {
  rl.close();
  engine.store.close();
}

