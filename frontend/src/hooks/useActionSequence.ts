import { useCallback, useState } from 'react';
import type { ActionEvent, ActionType, VillainPosition } from '../types/poker';

export const PREFLOP_POSITION_ORDER: Record<string, number> = {
  'UTG': 0,
  'UTG+1': 1,
  'MP': 2,
  'MP+1': 3,
  'HJ': 4,
  'CO': 5,
  'BTN': 6,
  'BTN/SB': 7,
  'SB': 8,
  'BB': 9,
};

export function sortActionSequence(sequence: ActionEvent[]): ActionEvent[] {
  return [...sequence].sort(
    (a, b) => (PREFLOP_POSITION_ORDER[a.position] ?? 0) - (PREFLOP_POSITION_ORDER[b.position] ?? 0)
  );
}

export function getValidActionsForSeat(sequenceBefore: ActionEvent[]): ActionType[] {
  const aggressiveCount = sequenceBefore.filter(
    (e) => e.action === 'OPEN' || e.action === 'PUSH' || e.action === 'THREE_BET'
  ).length;

  if (aggressiveCount >= 2) {
    return ['CALL', 'PUSH'];
  }

  if (aggressiveCount === 1) {
    return ['CALL', 'THREE_BET', 'PUSH'];
  }

  const hasLimp = sequenceBefore.some((e) => e.action === 'LIMP');
  if (hasLimp) {
    return ['LIMP', 'OPEN', 'PUSH'];
  }

  return ['OPEN', 'LIMP', 'PUSH'];
}

export function sanitizeSequence(sequence: ActionEvent[]): ActionEvent[] {
  const sorted = sortActionSequence(sequence);
  const result: ActionEvent[] = [];

  for (const event of sorted) {
    const validActions = getValidActionsForSeat(result);
    let action = event.action;

    if (!validActions.includes(action)) {
      action = validActions[0];
    }

    result.push({ position: event.position, action });
  }

  return result;
}

export function cycleActionSequence(sequence: ActionEvent[], position: VillainPosition): ActionEvent[] {
  const sorted = sortActionSequence(sequence);
  const index = sorted.findIndex((e) => e.position === position);

  if (index < 0) {
    const newUnsanitized = [...sorted, { position, action: 'OPEN' as ActionType }];
    return sanitizeSequence(newUnsanitized);
  }

  const sequenceBefore = sorted.slice(0, index);
  const validActions = getValidActionsForSeat(sequenceBefore);
  const currentAction = sorted[index].action;
  const currentValidIndex = validActions.indexOf(currentAction);

  if (currentValidIndex < 0 || currentValidIndex === validActions.length - 1) {
    const remaining = sorted.filter((e) => e.position !== position);
    return sanitizeSequence(remaining);
  }

  const nextAction = validActions[currentValidIndex + 1];
  const updated = sorted.map((e, i) => (i === index ? { ...e, action: nextAction } : e));
  return sanitizeSequence(updated);
}

export function useActionSequence() {
  const [actionSequence, setActionSequence] = useState<ActionEvent[]>([]);
  const cycleVillain = useCallback((position: VillainPosition) => {
    setActionSequence((current) => cycleActionSequence(current, position));
  }, []);
  const clear = useCallback(() => setActionSequence([]), []);
  return { actionSequence, cycleVillain, clear };
}