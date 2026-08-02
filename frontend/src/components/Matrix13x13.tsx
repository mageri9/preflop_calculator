import { useMemo } from 'react';
import { expandRangeStr, generate13x13Matrix } from '../utils/range';

export interface ActionRanges {
  push?: string;
  raise?: string;
  isolate?: string;
  call?: string;
}

export interface Matrix13x13Props {
  activeRangeStr?: string;
  selectedCombo?: string;
  onSelectCombo: (combo: string) => void;
  isLoading?: boolean;
  action?: string;
  actionRanges?: ActionRanges;
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
  const expandedPush = useMemo(() => expandRangeStr(actionRanges?.push), [actionRanges?.push]);
  const expandedRaise = useMemo(() => expandRangeStr(actionRanges?.raise), [actionRanges?.raise]);
  const expandedIsolate = useMemo(() => expandRangeStr(actionRanges?.isolate), [actionRanges?.isolate]);
  const expandedCall = useMemo(() => expandRangeStr(actionRanges?.call), [actionRanges?.call]);

  const hasActiveRange = Boolean(
    activeRangeStr?.trim() ||
      actionRanges?.push?.trim() ||
      actionRanges?.raise?.trim() ||
      actionRanges?.isolate?.trim() ||
      actionRanges?.call?.trim()
  );

  const getComboClass = (combo: string) => {
    const isSelected = selectedCombo === combo;

    if (isSelected) {
      return 'bg-amber-300 text-black font-extrabold ring-2 ring-white scale-105 z-20 shadow-lg';
    }

    if (expandedPush.has(combo)) {
      return 'bg-rose-600 text-white font-bold'; // КРАСНЫЙ ДЛЯ ПУША
    }
    if (expandedIsolate.has(combo)) {
      return 'bg-blue-600 text-white font-bold'; // СИНИЙ ДЛЯ ИЗОЛЕЙТА
    }
    if (expandedRaise.has(combo)) {
      return 'bg-amber-500 text-black font-bold'; // ЖЕЛТЫЙ ДЛЯ РЕЙЗА
    }
    if (expandedCall.has(combo)) {
      return 'bg-emerald-600 text-white font-bold'; // ЗЕЛЕНЫЙ ДЛЯ КОЛЛА
    }

    if (expandedActive.has(combo)) {
      switch (action) {
        case 'PUSH':
        case '3BET_PUSH':
          return 'bg-rose-600 text-white font-bold';
        case 'ISOLATE':
          return 'bg-blue-600 text-white font-bold';
        case 'OPEN_RAISE':
        case 'RAISE':
        case '3BET_RAISE':
        case 'BET':
          return 'bg-amber-500 text-black font-bold'; // ЖЕЛТЫЙ ДЛЯ РЕЙЗА
        case 'CALL':
        case 'DEFEND':
          return 'bg-emerald-600 text-white font-bold'; // ЗЕЛЕНЫЙ ДЛЯ КОЛЛА
        default:
          return 'bg-amber-500 text-black font-bold';
      }
    }

    return hasActiveRange
      ? 'bg-slate-900/90 text-slate-700'
      : 'bg-slate-800/80 text-slate-300 font-medium';
  };

  return (
    <div
      className={`mx-auto grid aspect-square w-full max-w-[360px] grid-cols-13 gap-[1px] rounded-lg bg-slate-950 p-1 select-none ${isLoading ? 'opacity-80' : ''}`}
      aria-busy={isLoading}
    >
      {matrix.flat().map((combo) => {
        const isSelected = selectedCombo === combo;
        const stateClass = getComboClass(combo);

        return (
          <button
            key={combo}
            type="button"
            onClick={() => onSelectCombo(combo)}
            className={`flex cursor-pointer items-center justify-center rounded-[2px] text-[9px] transition-all ${stateClass}`}
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