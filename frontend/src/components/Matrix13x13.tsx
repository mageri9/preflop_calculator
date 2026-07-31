import { useMemo } from 'react';
import { expandRangeStr, generate13x13Matrix } from '../utils/range';

export interface Matrix13x13Props {
  activeRangeStr?: string;
  selectedCombo?: string;
  onSelectCombo: (combo: string) => void;
  isLoading?: boolean;
}

export function Matrix13x13({
  activeRangeStr,
  selectedCombo,
  onSelectCombo,
  isLoading = false,
}: Matrix13x13Props) {
  const matrix = useMemo(() => generate13x13Matrix(), []);
  const expandedRange = useMemo(() => expandRangeStr(activeRangeStr), [activeRangeStr]);
  const hasActiveRange = Boolean(activeRangeStr?.trim());

  return (
    <div
      className={`mx-auto grid aspect-square w-full max-w-[360px] grid-cols-13 gap-[1px] rounded-lg bg-slate-950 p-1 select-none ${isLoading ? 'opacity-80' : ''}`}
      aria-busy={isLoading}
    >
      {matrix.flat().map((combo) => {
        const isInRange = expandedRange.has(combo);
        const isSelected = selectedCombo === combo;
        const stateClasses = isSelected
          ? 'bg-amber-400 text-black font-extrabold ring-1 ring-amber-300 scale-105 z-10'
          : isInRange
            ? 'bg-emerald-600 text-white font-bold'
            : hasActiveRange
              ? 'bg-slate-900/90 text-slate-700'
              : 'bg-slate-800/80 text-slate-300 font-medium';

        return (
          <button
            key={combo}
            type="button"
            onClick={() => onSelectCombo(combo)}
            className={`flex cursor-pointer items-center justify-center rounded-[2px] text-[9px] ${stateClasses}`}
            aria-label={`Выбрать ${combo}`}
            aria-pressed={isSelected}
          >
            {combo}
          </button>
        );
      })}
    </div>
  );
}
