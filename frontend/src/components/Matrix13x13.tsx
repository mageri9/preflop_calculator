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
  const expandedRange = useMemo(
    () => expandRangeStr(activeRangeStr),
    [activeRangeStr],
  );
  const hasActiveRange = Boolean(activeRangeStr?.trim());

  return (
    <div
      className={`grid grid-cols-13 gap-[2px] w-full max-w-[420px] mx-auto aspect-square p-1.5 bg-slate-900 rounded-xl shadow-2xl select-none ${isLoading ? 'opacity-80' : ''}`}
      aria-busy={isLoading}
    >
      {matrix.flat().map((combo) => {
        const isInRange = expandedRange.has(combo);
        const isSelected = selectedCombo === combo;
        const stateClasses = isSelected
          ? 'bg-amber-400 text-black font-extrabold ring-2 ring-amber-300 z-10 scale-105 shadow-lg shadow-amber-500/50'
          : isInRange
            ? 'bg-emerald-600 hover:bg-emerald-500 text-white font-bold'
            : hasActiveRange
              ? 'bg-slate-800/90 text-slate-600'
              : 'bg-slate-700/80 hover:bg-slate-600 text-slate-200 font-medium';

        return (
          <button
            key={combo}
            type="button"
            onClick={() => onSelectCombo(combo)}
            className={`text-[10px] sm:text-xs flex items-center justify-center rounded-[3px] transition-all duration-150 active:scale-95 cursor-pointer ${stateClasses}`}
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
