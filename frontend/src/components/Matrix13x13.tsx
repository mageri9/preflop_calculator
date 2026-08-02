import { useMemo } from 'react';
import { expandRangeStr, generate13x13Matrix } from '../utils/range';
import { ACTION_ORDER, getCellPresentation } from '../utils/matrixPresentation';

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

  return (
    <div
      className={`matrix-grid mx-auto grid aspect-square w-full max-w-[390px] grid-cols-13 gap-[1px] rounded-xl bg-slate-950 p-1 select-none ${isLoading ? 'opacity-70' : ''}`}
      aria-busy={isLoading}
      aria-label="Матрица стартовых рук 13 на 13"
    >
      {matrix.flat().map((combo) => {
        const isSelected = selectedCombo === combo;
        const presentation = getCellPresentation(combo, actionRanges, expandedActive, action);
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
