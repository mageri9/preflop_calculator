import assert from 'node:assert/strict';
import test from 'node:test';

import { cycleActionSequence } from '../src/hooks/useActionSequence.ts';
import type { ActionEvent } from '../src/types/poker.ts';

test('cycles actions for first seat (UTG) and removes it after complete cycle', () => {
  let sequence: ActionEvent[] = [];
  for (const action of ['OPEN', 'LIMP', 'PUSH']) {
    sequence = cycleActionSequence(sequence, 'UTG');
    assert.equal(sequence[0].action, action);
  }
  assert.deepEqual(cycleActionSequence(sequence, 'UTG'), []);
});

test('automatically sorts seats in preflop order and assigns valid actions facing an OPEN', () => {
  let sequence = cycleActionSequence([], 'UTG'); // UTG: OPEN
  sequence = cycleActionSequence(sequence, 'CO'); // Facing OPEN: default is CALL
  assert.deepEqual(sequence, [
    { position: 'UTG', action: 'OPEN' },
    { position: 'CO', action: 'CALL' },
  ]);

  sequence = cycleActionSequence(sequence, 'CO'); // Click CO again -> THREE_BET
  assert.equal(sequence[1].action, 'THREE_BET');
});

test('auto-sorts seats clicked out of order', () => {
  let sequence = cycleActionSequence([], 'SB');
  sequence = cycleActionSequence(sequence, 'UTG');
  assert.deepEqual(sequence, [
    { position: 'UTG', action: 'OPEN' },
    { position: 'SB', action: 'CALL' },
  ]);
});

test('handles limp-chain sequence (LIMP -> LIMP -> OPEN)', () => {
  let sequence = cycleActionSequence([], 'UTG');
  sequence = cycleActionSequence(sequence, 'UTG'); // UTG: LIMP
  sequence = cycleActionSequence(sequence, 'MP');  // Facing LIMP: default is LIMP
  sequence = cycleActionSequence(sequence, 'CO');  // Facing LIMP: default is LIMP
  sequence = cycleActionSequence(sequence, 'CO');  // CO cycles to OPEN (isolate raise)

  assert.deepEqual(sequence, [
    { position: 'UTG', action: 'LIMP' },
    { position: 'MP', action: 'LIMP' },
    { position: 'CO', action: 'OPEN' },
  ]);
});