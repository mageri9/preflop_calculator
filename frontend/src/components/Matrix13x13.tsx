import { useMemo, type CSSProperties } from 'react';
import { expandRangeStr, generate13x13Matrix } from '../utils/range';

export type RangeAction = 'push' | 'raise' | 'isolate' | 'call';
export type ActionRanges = Record<RangeAction, Record<string, number>>;

export interface Matrix13x13Props {
  activeRangeStr?: string;
  selectedCombo?: string;
  onSelectCombo: (combo: string) => void;
  isLoading?: boolean;
  action?: string;
  actionRanges?: Partial<ActionRanges>;
}

const ACTION_COLORS: Record<RangeAction, string> = {
  push: '#e11d48',
  raise: '#f59e0b',
  isolate: '#2563eb',
  call: '#059669',
};

const ACTION_ORDER: RangeAction[] = ['push', 'raise', 'isolate', 'call'];

function clampFrequency(value: number | undefined): number {
  return Math.max(0, Math.min(100, Number(value) || 0));
}

function actionFromDecision(action?: string): RangeAction {
  if (action === 'PUSH' || action === '3BET_PUSH') return 'push';
  if (action === 'ISOLATE') return 'isolate';
  if (action === 'CALL' || action === 'DEFEND') return 'call';
  return 'raise';
}

export function Matrix13x13({
  activeRangeStr,
  selectedCombo,
  onSelectCombo,
  isLoading = false,
  action,
  actionRanges,
}: Matrix13x13Props) {
  const matrix = useMemo(() => generate13x13Matrix(), []);
  const expandedActive = useMemo(() => expandRangeStr(activeRangeStr), [activeRangeStr]);
  const hasFrequencyData = ACTION_ORDER.some(
    (rangeAction) => Object.keys(actionRanges?.[rangeAction] ?? {}).length > 0,
  );

  const getCellPresentation = (combo: string): { style?: CSSProperties; inactive: boolean; title: string } => {
    const frequencies = ACTION_ORDER.map((rangeAction) => ({
      action: rangeAction,
      value: clampFrequency(actionRanges?.[rangeAction]?.[combo]),
    })).filter(({ value }) => value > 0);

    if (!frequencies.length && expandedActive.has(combo)) {
      frequencies.push({ action: actionFromDecision(action), value: 100 });
    }

    if (!frequencies.length) {
      return { inactive: true, title: `${combo}: FOLD 100%` };
    }

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
  };

  return (
    <div
      className={`matrix-grid mx-auto grid aspect-square w-full max-w-[390px] grid-cols-13 gap-[1px] rounded-xl bg-slate-950 p-1 select-none ${isLoading ? 'opacity-70' : ''}`}
      aria-busy={isLoading}
      aria-label="Матрица стартовых рук 13 на 13"
    >
      {matrix.flat().map((combo) => {
        const isSelected = selectedCombo === combo;
        const presentation = getCellPresentation(combo);
        const inactive = presentation.inactive && (hasFrequencyData || Boolean(activeRangeStr));

        return (
          <button
            key={combo}
            type="button"
            onClick={() => onSelectCombo(combo)}
            style={presentation.style}
            title={presentation.title}
            className={`matrix-cell relative flex min-h-[24px] touch-manipulation items-center justify-center rounded-[3px] font-mono text-[clamp(7px,2.35vw,10px)] font-extrabold leading-none transition-[transform,filter] active:scale-90 ${
              isSelected
                ? 'z-20 scale-110 text-white ring-2 ring-white shadow-lg brightness-125'
                : inactive
                  ? 'bg-slate-900/90 text-slate-600'
                  : presentation.inactive
                    ? 'bg-slate-800/80 text-slate-300'
                    : 'text-white shadow-inner'
            }`}
            aria-label={presentation.title}
            aria-pressed={isSelected}
          >
            {combo}
          </button>
        );
      })}
    </div>
  );
}
