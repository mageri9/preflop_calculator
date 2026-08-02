import type { CSSProperties } from 'react';
import type { ActionRanges, RangeAction } from '../components/Matrix13x13';

const ACTION_COLORS: Record<RangeAction, string> = {
  push: '#e11d48',
  raise: '#f59e0b',
  isolate: '#2563eb',
  call: '#059669',
};

export const ACTION_ORDER: RangeAction[] = ['push', 'raise', 'isolate', 'call'];

function clampFrequency(value: number | undefined): number {
  return Math.max(0, Math.min(100, Number(value) || 0));
}

function actionFromDecision(action?: string): RangeAction {
  if (action === 'PUSH' || action === '3BET_PUSH') return 'push';
  if (action === 'ISOLATE') return 'isolate';
  if (action === 'CALL' || action === 'DEFEND') return 'call';
  return 'raise';
}

export function getCellPresentation(
  combo: string,
  actionRanges: Partial<ActionRanges> | undefined,
  expandedActive: Set<string>,
  action?: string,
): { style?: CSSProperties; inactive: boolean; title: string } {
  const frequencies = ACTION_ORDER.map((rangeAction) => ({
    action: rangeAction,
    value: clampFrequency(actionRanges?.[rangeAction]?.[combo]),
  })).filter(({ value }) => value > 0);

  if (!frequencies.length && expandedActive.has(combo)) {
    frequencies.push({ action: actionFromDecision(action), value: 100 });
  }
  if (!frequencies.length) return { inactive: true, title: `${combo}: FOLD 100%` };

  let cursor = 0;
  const stops: string[] = [];
  for (const frequency of frequencies) {
    const end = Math.min(100, cursor + frequency.value);
    stops.push(`${ACTION_COLORS[frequency.action]} ${cursor}% ${end}%`);
    cursor = end;
  }
  if (cursor < 100) stops.push(`#111827 ${cursor}% 100%`);

  const title = frequencies
    .map(({ action: rangeAction, value }) => `${rangeAction.toUpperCase()} ${value}%`)
    .concat(cursor < 100 ? [`FOLD ${Math.round((100 - cursor) * 100) / 100}%`] : [])
    .join(' / ');
  return {
    inactive: false,
    style: { background: `linear-gradient(135deg, ${stops.join(', ')})` },
    title: `${combo}: ${title}`,
  };
}
