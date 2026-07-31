import { useState } from 'react';

export interface FlopPickerProps {
  flopCards: string[];
  onFlopChange: (cards: string[]) => void;
}

const ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'] as const;
const suits = [
  { code: 's', symbol: '♠', label: 'Пики', color: 'text-slate-900' },
  { code: 'h', symbol: '♥', label: 'Червы', color: 'text-rose-500' },
  { code: 'd', symbol: '♦', label: 'Бубны', color: 'text-sky-500' },
  { code: 'c', symbol: '♣', label: 'Трефы', color: 'text-emerald-600' },
] as const;

export const formatCard = (card: string) => {
  const suit = suits.find(({ code }) => code === card[1]);
  return `${card[0]}${suit?.symbol ?? ''}`;
};

export function FlopPicker({ flopCards, onFlopChange }: FlopPickerProps) {
  const [selectedRank, setSelectedRank] = useState('K');
  const complete = flopCards.length === 3;

  const selectSuit = (suit: string) => {
    const card = `${selectedRank}${suit}`;
    if (!complete && !flopCards.includes(card)) onFlopChange([...flopCards, card]);
  };

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/80 p-4 shadow-2xl backdrop-blur" aria-label="Выбор флопа">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-emerald-400">Быстрый 3-tap селектор</p>
          <h2 className="mt-1 text-lg font-black text-white">Введите карты флопа</h2>
        </div>
        <button type="button" disabled={!flopCards.length} onClick={() => onFlopChange([])} className="rounded-xl bg-white/5 px-3 py-2 text-xs font-bold text-slate-400 disabled:opacity-30">Сбросить</button>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2">
        {[0, 1, 2].map((index) => {
          const card = flopCards[index];
          const suit = suits.find(({ code }) => code === card?.[1]);
          return (
            <button key={index} type="button" disabled={!card} onClick={() => onFlopChange(flopCards.filter((_, i) => i !== index))} className="flex h-16 items-center justify-center rounded-2xl border border-white/10 bg-stone-50 text-2xl font-black text-slate-900 shadow-lg disabled:border-dashed disabled:bg-white/[0.03] disabled:text-slate-600 disabled:shadow-none">
              {card ? <><span>{card[0]}</span><span className={suit?.color}>{suit?.symbol}</span></> : <span className="text-sm">Карта {index + 1}</span>}
            </button>
          );
        })}
      </div>

      <p className="mb-2 mt-4 text-[10px] font-bold uppercase tracking-wider text-slate-500">Ранг</p>
      <div className="grid grid-cols-7 gap-1 sm:grid-cols-13">
        {ranks.map((rank) => <button key={rank} type="button" disabled={complete} onClick={() => setSelectedRank(rank)} className={`rounded-lg py-2 text-xs font-black ${selectedRank === rank ? 'bg-amber-400 text-black' : 'bg-white/5 text-slate-300'} disabled:opacity-30`}>{rank}</button>)}
      </div>

      <p className="mb-2 mt-4 text-[10px] font-bold uppercase tracking-wider text-slate-500">Масть для {selectedRank}</p>
      <div className="grid grid-cols-4 gap-2">
        {suits.map(({ code, symbol, label, color }) => <button key={code} type="button" disabled={complete || flopCards.includes(`${selectedRank}${code}`)} onClick={() => selectSuit(code)} className="rounded-xl bg-stone-50 py-2 text-xs font-black text-slate-700 disabled:opacity-25"><span className={`mr-1 text-lg ${color}`}>{symbol}</span>{label}</button>)}
      </div>
    </section>
  );
}
