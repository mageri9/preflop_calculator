import type { TableSession } from '../types/poker';

export interface TableControlsProps {
  session: TableSession;
  onNextHand: () => void;
  onChangeTableSize: (newSize: number) => void;
  onUpdateSession: (payload: Partial<TableSession>) => void;
  isLoading?: boolean;
}

const toggleBase =
  'rounded-lg px-2.5 py-2 text-xs font-bold transition disabled:cursor-wait disabled:opacity-50';

export function TableControls({
  session,
  onNextHand,
  onChangeTableSize,
  onUpdateSession,
  isLoading = false,
}: TableControlsProps) {
  const bbInChips =
    session.stack_bb > 0
      ? Math.max(1, Math.round(session.stack_chips / session.stack_bb))
      : 100;

  const changeStackBB = (deltaBB: number) => {
    const newBB = Math.max(1, session.stack_bb + deltaBB);
    const newChips = Math.max(1, Math.round(newBB * bbInChips));
    onUpdateSession({ stack_chips: newChips });
  };

  const toggleClass = (active: boolean) =>
    `${toggleBase} ${
      active
        ? 'bg-emerald-500 text-emerald-950 shadow-md shadow-emerald-950/30'
        : 'bg-white/[0.06] text-white/70 hover:bg-white/10'
    }`;

  return (
    <section className="space-y-3 rounded-2xl border border-white/10 bg-slate-950/60 p-3.5 backdrop-blur-md">
      <button
        type="button"
        disabled={isLoading}
        onClick={onNextHand}
        className="w-full rounded-xl bg-amber-400 px-4 py-3 text-sm font-black text-amber-950 shadow-md shadow-amber-950/40 transition active:scale-[0.98] hover:bg-amber-300 disabled:opacity-50"
      >
        ♠️ Следующая раздача (BTN +1)
      </button>

      <div className="rounded-xl border border-white/10 bg-white/[0.03] p-2.5">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-[10px] font-bold uppercase tracking-widest text-white/40">
            Стек в блайндах
          </span>
          <div className="text-right">
            <span className="text-lg font-black text-emerald-400">
              {session.stack_bb} BB
            </span>
            <span className="block text-[10px] text-white/30">
              ({session.stack_chips.toLocaleString()} фишек)
            </span>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2">
          <button
            type="button"
            disabled={isLoading || session.stack_bb <= 1}
            onClick={() => changeStackBB(-1)}
            className={toggleClass(false)}
          >
            ◀️ -1 BB
          </button>
          <button
            type="button"
            disabled={isLoading}
            onClick={() => changeStackBB(1)}
            className={toggleClass(false)}
          >
            +1 BB ▶️
          </button>
          <button
            type="button"
            disabled={isLoading}
            onClick={() =>
              onUpdateSession({ blind_level: session.blind_level + 1 })
            }
            className={toggleClass(false)}
          >
            📈 Блайнды UP
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <button
          type="button"
          disabled={isLoading || session.table_size <= 2}
          onClick={() => onChangeTableSize(session.table_size - 1)}
          className={toggleClass(false)}
        >
          👥 -1 Игрок ({session.table_size - 1}-max)
        </button>
        <button
          type="button"
          disabled={isLoading || session.table_size >= 9}
          onClick={() => onChangeTableSize(session.table_size + 1)}
          className={toggleClass(false)}
        >
          👥 +1 Игрок ({session.table_size + 1}-max)
        </button>
      </div>

      <div className="space-y-2">
        <div>
          <p className="mb-1 text-[10px] font-bold uppercase tracking-widest text-white/40">
            ICM стадия
          </p>
          <div className="grid grid-cols-3 gap-1.5">
            {([
              ['Normal', 'NORMAL'],
              ['Bubble', 'BUBBLE'],
              ['Final Table', 'FINAL_TABLE'],
            ] as const).map(([label, value]) => (
              <button
                key={value}
                type="button"
                disabled={isLoading}
                onClick={() => onUpdateSession({ icm_stage: value })}
                className={toggleClass(session.icm_stage === value)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <p className="mb-1 text-[10px] font-bold uppercase tracking-widest text-white/40">
            Стиль оппонентов
          </p>
          <div className="grid grid-cols-3 gap-1.5">
            {(['REG', 'TIGHT', 'LOOSE'] as const).map((value) => (
              <button
                key={value}
                type="button"
                disabled={isLoading}
                onClick={() => onUpdateSession({ opponent_style: value })}
                className={toggleClass(session.opponent_style === value)}
              >
                {value === 'REG'
                  ? 'Reg'
                  : value === 'TIGHT'
                    ? 'Tight'
                    : 'Loose'}
              </button>
            ))}
          </div>
        </div>

        <button
          type="button"
          disabled={isLoading}
          onClick={() => onUpdateSession({ has_ante: !session.has_ante })}
          className={`w-full ${toggleClass(session.has_ante)}`}
          aria-pressed={session.has_ante}
        >
          Ante: {session.has_ante ? 'ON' : 'OFF'}
        </button>
      </div>
    </section>
  );
}
