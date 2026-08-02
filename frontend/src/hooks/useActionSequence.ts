import { useCallback, useState } from 'react';
import type { ActionEvent, ActionType, VillainPosition } from '../types/poker';

export const ACTION_CYCLE: readonly ActionType[] = ['OPEN', 'THREE_BET', 'LIMP', 'PUSH'];

export function cycleActionSequence(sequence: ActionEvent[], position: VillainPosition): ActionEvent[] {
  const index = sequence.findIndex((event) => event.position === position);
  if (index < 0) return [...sequence, { position, action: 'OPEN' }];
  const nextAction = ACTION_CYCLE[ACTION_CYCLE.indexOf(sequence[index].action) + 1];
  if (!nextAction) return sequence.filter((_, eventIndex) => eventIndex !== index);
  return sequence.map((event, eventIndex) => eventIndex === index ? { ...event, action: nextAction } : event);
}

export function useActionSequence() {
  const [actionSequence, setActionSequence] = useState<ActionEvent[]>([]);
  const cycleVillain = useCallback((position: VillainPosition) => {
    setActionSequence((current) => cycleActionSequence(current, position));
  }, []);
  const clear = useCallback(() => setActionSequence([]), []);
  return { actionSequence, cycleVillain, clear };
}
