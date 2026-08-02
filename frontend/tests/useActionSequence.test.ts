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

test('handles push -> re-push -> call sequence', () => {
  let sequence = cycleActionSequence([], 'UTG'); // UTG: OPEN
  sequence = cycleActionSequence(sequence, 'UTG'); // UTG: LIMP
  sequence = cycleActionSequence(sequence, 'UTG'); // UTG: PUSH

  sequence = cycleActionSequence(sequence, 'BTN'); // BTN facing PUSH: default is CALL
  sequence = cycleActionSequence(sequence, 'BTN'); // BTN cycles CALL -> THREE_BET
  sequence = cycleActionSequence(sequence, 'BTN'); // BTN cycles THREE_BET -> PUSH (re-shove)

  sequence = cycleActionSequence(sequence, 'SB');  // SB facing 2 aggressive actions: default is CALL
  sequence = cycleActionSequence(sequence, 'BB');  // BB facing 2 aggressive actions: default is CALL

  assert.deepEqual(sequence, [
    { position: 'UTG', action: 'PUSH' },
    { position: 'BTN', action: 'PUSH' },
    { position: 'SB', action: 'CALL' },
    { position: 'BB', action: 'CALL' },
  ]);
});