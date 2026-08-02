import assert from 'node:assert/strict';
import test from 'node:test';

import { cycleActionSequence } from '../src/hooks/useActionSequence.ts';
import type { ActionEvent } from '../src/types/poker.ts';

test('cycles actions and removes a seat after the complete cycle', () => {
  let sequence: ActionEvent[] = [];
  for (const action of ['OPEN', 'THREE_BET', 'LIMP', 'PUSH']) {
    sequence = cycleActionSequence(sequence, 'UTG');
    assert.equal(sequence[0].action, action);
  }
  assert.deepEqual(cycleActionSequence(sequence, 'UTG'), []);
});

test('updates a seat without changing click order', () => {
  let sequence = cycleActionSequence([], 'UTG');
  sequence = cycleActionSequence(sequence, 'CO');
  sequence = cycleActionSequence(sequence, 'UTG');
  assert.deepEqual(sequence.map((event) => event.position), ['UTG', 'CO']);
  assert.equal(sequence[0].action, 'THREE_BET');
});
