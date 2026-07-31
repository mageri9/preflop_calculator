import type { DecisionResult } from '../types/poker';

export interface PostflopViewProps {
  result: DecisionResult | null;
  potType: 'SRP' | '3BP';
  heroRole: 'PFR' | 'PFC';
  heroPosition: 'IP' | 'OOP';
  onUpdateContext: (payload: {
    potType?: 'SRP' | '3BP';
    heroRole?: 'PFR' | 'PFC';
    heroPosition?: 'IP' | 'OOP';
  }) => void;
  isLoading?: boolean;
}

const toggleClass = (active: boolean) =>
  `rounded-lg px-3 py-2 text-xs font-black transition disabled:cursor-wait disabled:opacity-50 ${
    active
      ? 'bg-emerald-400 text-emerald-950 shadow-md shadow-emerald-950/30'
      : 'bg-white/[0.06] text-white/60 hover:bg-white/10'
  }`;

export function PostflopView({
  result,
  potType,
  heroRole,
  heroPosition,
  onUpdateContext,
  isLoading = false,
}: PostflopViewProps) {
  const groups = [
    {
      label: 'Тип банка',
      values: [
        ['SRP', 'Single Raised Pot'],
        ['3BP', '3-Bet Pot'],
      ] as const,
      current: potType,
      update: (value: 'SRP' | '3BP') => onUpdateContext({ potType: value }),
    },
    {
      label: 'Роль Хиро',
      values: [
        ['PFR', 'Preflop Aggressor'],
        ['PFC', 'Preflop Caller'],
      ] as const,
      current: heroRole,
      update: (value: 'PFR' | 'PFC') => onUpdateContext({ heroRole: value }),
    },
    {
      label: 'Позиция',
      values: [
        ['IP', 'In Position'],
        ['OOP', 'Out of Position'],
      ] as const,
      current: heroPosition,
      update: (value: 'IP' | 'OOP') => onUpdateContext({ heroPosition: value }),
    },
  ];

  const frequencies = [
    { label: 'CHECK', value: result?.frequencies?.check_pct ?? 0, color: 'bg-slate-400' },
    { label: 'BET', value: result?.frequencies?.bet_pct ?? 0, color: 'bg-emerald-400' },
    { label: 'RAISE', value: result?.frequencies?.raise_pct ?? 0, color: 'bg-amber-400' },
  ];
  const details = result?.details;

  return (
    <section className="rounded-2xl border border-white/10 bg-slate-950/60 p-4 backdrop-blur-md" aria-busy={isLoading}>
      <div className="space-y-3">
        {groups.map((group) => (
          <div key={group.label}>
            <p className="mb-1.5 text-[10px] font-bold uppercase tracking-[0.2em] text-white/40">{group.label}</p>
            <div className="grid grid-cols-2 gap-2">
              {group.values.map(([value, description]) => (
                <button
                  key={value}
                  type="button"
                  disabled={isLoading}
                  onClick={() => group.update(value as never)}
                  className={toggleClass(group.current === value)}
                  aria-pressed={group.current === value}
                >
                  <span className="block">{value}</span>
                  <span className="mt-0.5 block text-[9px] font-medium opacity-60">{description}</span>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      {isLoading && (
        <div className="mt-5 animate-pulse rounded-xl border border-mint/20 bg-mint/5 p-5 text-center text-sm font-bold text-mint">
          Рассчитываем GTO-линию…
        </div>
      )}

      {!isLoading && !result && (
        <div className="mt-5 rounded-xl border border-dashed border-white/15 p-5 text-center text-sm text-white/40">
          Выберите три карты флопа, чтобы увидеть стратегию.
        </div>
      )}

      {!isLoading && result && (
        <div className="mt-5 space-y-5">
          {details && (
            <div className="flex flex-wrap gap-2">
              {[
                ['Текстура', details.texture_id],
                ['Рука', details.bucket_id],
                ['Стек', details.stack_depth],
              ].map(([label, value]) => value != null && (
                <span key={label} className="rounded-full border border-white/10 bg-white/[0.06] px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-white/65">
                  <span className="mr-1 text-white/30">{label}:</span> {String(value)}
                </span>
              ))}
            </div>
          )}

          {result.frequencies && (
            <div className="space-y-3">
              {frequencies.map(({ label, value, color }) => {
                const percentage = Math.min(100, Math.max(0, value));
                return (
                  <div key={label}>
                    <div className="mb-1 flex justify-between text-xs font-bold">
                      <span className="text-white/55">{label}</span>
                      <span className="text-cream">{percentage.toFixed(1)}%</span>
                    </div>
                    <div className="h-2.5 overflow-hidden rounded-full bg-white/[0.06]">
                      <div className={`h-full rounded-full ${color} transition-[width] duration-500`} style={{ width: `${percentage}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <div className="overflow-hidden rounded-2xl border border-amber-300/25 bg-gradient-to-br from-amber-400/20 to-emerald-400/10 p-5 text-center shadow-lg shadow-black/20">
            <p className="text-[10px] font-bold uppercase tracking-[0.25em] text-white/40">Рекомендованное действие</p>
            <p className="mt-2 font-display text-3xl font-bold text-amber-300">
              {result.recommended_sizing || result.action}
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
