import { useState } from 'react';
import type { TableSession } from '../types/poker';

export interface TableControlsProps {
  session: TableSession;
  onNextHand: () => void;
  onChangeTableSize: (newSize: number) => void;
  onUpdateSession: (payload: Partial<TableSession>) => void;
  isLoading?: boolean;
}

const buttonClass =
  'rounded-lg bg-slate-800 px-2 py-1.5 text-[10px] font-bold text-slate-300 transition hover:bg-slate-700 disabled:cursor-wait disabled:opacity-40';

export function TableControls({
  session,
  onNextHand,
  onChangeTableSize,
  onUpdateSession,
  isLoading = false,
}: TableControlsProps) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const bbInChips = session.stack_bb > 0
    ? Math.max(1, Math.round(session.stack_chips / session.stack_bb))
    : 100;

  const changeStackBB = (deltaBB: number) => {
    const stackBB = Math.max(1, session.stack_bb + deltaBB);
    onUpdateSession({ stack_chips: Math.max(1, Math.round(stackBB * bbInChips)) });
  };

  return (
    <section className="mx-auto w-full max-w-[360px] space-y-1.5">
      <button
        type="button"
        disabled={isLoading}
        onClick={onNextHand}
        className="w-full rounded-lg bg-amber-400 py-2 text-xs font-bold text-black transition hover:bg-amber-300 disabled:opacity-50"
      >
        Сдать раздачу (BTN +1)
      </button>

      <div className="flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900/70 p-1.5">
        <strong className="mr-auto whitespace-nowrap px-1 text-lg text-emerald-400">
          {session.stack_bb} BB
        </strong>
        <button type="button" disabled={isLoading || session.stack_bb <= 1} onClick={() => changeStackBB(-1)} className={buttonClass}>
          -1 BB
        </button>
        <button type="button" disabled={isLoading} onClick={() => changeStackBB(1)} className={buttonClass}>
          +1 BB
        </button>
        <button
          type="button"
          disabled={isLoading}
          onClick={() => onUpdateSession({ blind_level: session.blind_level + 1 })}
          className={buttonClass}
        >
          Блайнды +1
        </button>
      </div>

      <button
        type="button"
        onClick={() => setSettingsOpen((open) => !open)}
        className="w-full rounded-lg border border-slate-800 bg-slate-900 px-2 py-1.5 text-left text-[10px] font-medium text-slate-400"
        aria-expanded={settingsOpen}
      >
        Настройки: {session.table_size}-max | Ante: {session.has_ante ? 'ON' : 'OFF'} | {session.icm_stage}
      </button>

      {settingsOpen && (
        <div className="grid grid-cols-2 gap-1.5 rounded-lg border border-slate-800 bg-slate-900 p-2 text-[10px]">
          <label className="space-y-1 text-slate-500">
            Размер стола
            <select
              value={session.table_size}
              disabled={isLoading}
              onChange={(event) => onChangeTableSize(Number(event.target.value))}
              className="block w-full rounded bg-slate-800 p-1.5 text-slate-200"
            >
              {Array.from({ length: 8 }, (_, index) => index + 2).map((size) => (
                <option key={size} value={size}>{size}-max</option>
              ))}
            </select>
          </label>
          <label className="space-y-1 text-slate-500">
            ICM
            <select
              value={session.icm_stage}
              disabled={isLoading}
              onChange={(event) => onUpdateSession({ icm_stage: event.target.value as TableSession['icm_stage'] })}
              className="block w-full rounded bg-slate-800 p-1.5 text-slate-200"
            >
              <option value="NORMAL">Normal</option>
              <option value="BUBBLE">Bubble</option>
              <option value="FINAL_TABLE">Final Table</option>
            </select>
          </label>
          <label className="space-y-1 text-slate-500">
            Оппоненты
            <select
              value={session.opponent_style}
              disabled={isLoading}
              onChange={(event) => onUpdateSession({ opponent_style: event.target.value as TableSession['opponent_style'] })}
              className="block w-full rounded bg-slate-800 p-1.5 text-slate-200"
            >
              <option value="REG">Reg</option>
              <option value="TIGHT">Tight</option>
              <option value="LOOSE">Loose</option>
            </select>
          </label>
          <button
            type="button"
            disabled={isLoading}
            onClick={() => onUpdateSession({ has_ante: !session.has_ante })}
            className={`${buttonClass} self-end ${session.has_ante ? 'bg-emerald-600 text-white' : ''}`}
          >
            Ante: {session.has_ante ? 'ON' : 'OFF'}
          </button>
        </div>
      )}
    </section>
  );
}
