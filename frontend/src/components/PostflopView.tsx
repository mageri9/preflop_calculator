import type { DecisionResult } from '../types/poker';
import { formatCard } from './FlopPicker';

type PotType = 'SRP' | '3BP';
type HeroRole = 'PFR' | 'PFC';
type HeroPosition = 'IP' | 'OOP';

export interface PostflopViewProps {
  result: DecisionResult | null;
  flopCards: string[];
  heroCombo?: string;
  stackBB: number;
  potType: PotType;
  heroRole: HeroRole;
  heroPosition: HeroPosition;
  onUpdateContext: (payload: { potType?: PotType; heroRole?: HeroRole; heroPosition?: HeroPosition }) => void;
  onEditFlop: () => void;
  onNextHand: () => void;
  isLoading?: boolean;
}

const contextOptions = [
  { key: 'potType', label: 'Банк', values: [['SRP', 'SRP'], ['3BP', '3-Bet Pot']] },
  { key: 'heroRole', label: 'Хиро', values: [['PFR', 'PFR · Агрессор'], ['PFC', 'PFC · Коллер']] },
  { key: 'heroPosition', label: 'Позиция', values: [['IP', 'IP'], ['OOP', 'OOP']] },
] as const;

export function PostflopView(props: PostflopViewProps) {
  const { result, flopCards, heroCombo, stackBB, potType, heroRole, heroPosition, onUpdateContext, onEditFlop, onNextHand, isLoading } = props;
  const potBB = potType === 'SRP' ? 5.5 : 11;
  const sizingMatch = result?.recommended_sizing?.match(/(\d+)%/);
  const sizingPct = sizingMatch ? Number(sizingMatch[1]) : undefined;
  const sizingBB = sizingPct ? (potBB * sizingPct / 100).toFixed(1) : undefined;

  const frequencies = [
    ['BET', result?.frequencies?.BET ?? result?.frequencies?.bet_pct ?? 0, 'bg-amber-400'],
    ['CHECK', result?.frequencies?.CHECK ?? result?.frequencies?.check_pct ?? 0, 'bg-sky-400'],
    ['RAISE', result?.frequencies?.RAISE ?? result?.frequencies?.raise_pct ?? 0, 'bg-amber-400'],
    ['CALL', result?.frequencies?.CALL ?? 0, 'bg-emerald-400'],
  ] as const;

  const current = { potType, heroRole, heroPosition };

  if (!result || isLoading) return <div className="rounded-2xl border border-dashed border-white/15 p-5 text-center text-sm text-slate-400">{isLoading ? 'Evaluator анализирует текстуру и категорию руки…' : 'Выберите три карты флопа.'}</div>;

  return (
    <section className="overflow-hidden rounded-3xl border border-white/10 bg-slate-900/90 shadow-2xl">
      <div className="border-b border-white/10 p-4">
        <div className="flex items-start justify-between gap-3">
          <div><p className="text-xs font-bold text-slate-500">ФЛОП</p><p className="mt-1 text-2xl font-black tracking-wide">{flopCards.map(formatCard).join('  ')}</p></div>
          <div className="text-right text-xs text-slate-400"><p>Банк: <b className="text-white">{potBB} BB</b></p><p>Эфф. стек: <b className="text-white">{stackBB} BB</b></p></div>
        </div>
        <div className="mt-3 grid grid-cols-3 gap-1.5">
          {contextOptions.map((group) => <label key={group.key} className="text-[9px] font-bold uppercase tracking-wider text-slate-500">{group.label}<select value={current[group.key]} onChange={(event) => onUpdateContext({ [group.key]: event.target.value } as never)} className="mt-1 block w-full rounded-lg bg-white/5 p-2 text-[10px] font-bold normal-case text-slate-200 outline-none">{group.values.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>)}
        </div>
        <div className="mt-3 flex flex-wrap gap-2 text-[10px] font-bold uppercase">
          <span className="rounded-full bg-emerald-400/10 px-2.5 py-1 text-emerald-300">{result.details.texture_id}</span>
          <span className="rounded-full bg-amber-400/10 px-2.5 py-1 text-amber-300">{result.details.bucket_id} · {heroCombo}</span>
        </div>
      </div>

      <div className="p-4">
        <p className="text-[10px] font-black uppercase tracking-[0.2em] text-amber-400">Рекомендуемое действие</p>
        <p className="mt-1 text-3xl font-black text-white">{result.action}</p>
        <div className="mt-4 space-y-3">
          {frequencies.filter(([, value]) => Number(value) > 0).map(([label, value, color]) => <div key={label}><div className="mb-1 flex justify-between text-xs font-bold"><span>{label}</span><span>{value}%</span></div><div className="h-2 overflow-hidden rounded-full bg-white/5"><div className={`h-full rounded-full ${color} transition-all duration-500`} style={{ width: `${value}%` }} /></div></div>)}
        </div>
        <div className="mt-4 rounded-2xl border border-amber-400/20 bg-amber-400/10 p-3">
          <p className="text-xs text-slate-400">Оптимальный сайзинг</p>
          <p className="mt-1 text-lg font-black text-amber-300">{sizingPct ? `${sizingPct}% POT${sizingBB ? ` · ${sizingBB} BB` : ''}` : result.recommended_sizing}</p>
        </div>
      </div>
      <div className="grid grid-cols-2 border-t border-white/10">
        <button type="button" onClick={onEditFlop} className="p-3 text-xs font-bold text-slate-300">Изменить флоп</button>
        <button type="button" onClick={onNextHand} className="border-l border-white/10 bg-emerald-400/10 p-3 text-xs font-bold text-emerald-300">Следующая раздача</button>
      </div>
    </section>
  );
}