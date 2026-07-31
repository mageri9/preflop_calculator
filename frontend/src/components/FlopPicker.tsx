import { useMemo, useState } from 'react';

export interface FlopPickerProps {
  flopCards: string[];
  onFlopChange: (cards: string[]) => void;
  heroCombo?: string;
}

const ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'] as const;
const suits = [
  { code: 's', symbol: '♠', label: 'Пики', color: 'text-slate-900' },
  { code: 'h', symbol: '♥', label: 'Черви', color: 'text-red-500' },
  { code: 'd', symbol: '♦', label: 'Бубны', color: 'text-sky-500' },
  { code: 'c', symbol: '♣', label: 'Трефы', color: 'text-emerald-600' },
] as const;

const concreteCards = (combo?: string) =>
  combo?.match(/(?:[AKQJT2-9][shdc])/gi)?.map((card) => `${card[0].toUpperCase()}${card[1].toLowerCase()}`) ?? [];

export function FlopPicker({ flopCards, onFlopChange, heroCombo }: FlopPickerProps) {
  const [selectedRank, setSelectedRank] = useState<string>('A');
  const unavailableCards = useMemo(
    () => new Set([...flopCards, ...concreteCards(heroCombo)]),
    [flopCards, heroCombo],
  );

  const selectSuit = (suit: string) => {
    const card = `${selectedRank}${suit}`;
    if (flopCards.length < 3 && !unavailableCards.has(card)) {
      onFlopChange([...flopCards, card]);
    }
  };

  return (
    <section className="rounded-2xl border border-white/10 bg-slate-950/60 p-4 backdrop-blur-md">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-white/40">Борд</p>
          <h2 className="font-display text-2xl text-cream">Карты флопа</h2>
        </div>
        <span className="rounded-full bg-white/[0.06] px-3 py-1 text-xs font-bold text-white/50">
          {flopCards.length} / 3
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2" aria-label="Выбранные карты флопа">
        {[0, 1, 2].map((index) => {
          const card = flopCards[index];
          const suit = suits.find(({ code }) => code === card?.[1]);
          return card && suit ? (
            <button
              key={`${card}-${index}`}
              type="button"
              onClick={() => onFlopChange(flopCards.filter((_, cardIndex) => cardIndex !== index))}
              className="group min-h-24 rounded-xl border border-white/15 bg-stone-50 px-2 shadow-lg transition hover:-translate-y-0.5 hover:border-red-300"
              aria-label={`Убрать ${card}`}
            >
              <span className={`block text-3xl font-black ${suit.color}`}>{card[0]}</span>
              <span className={`block text-3xl leading-none ${suit.color}`}>{suit.symbol}</span>
              <span className="mt-1 block text-[9px] font-bold uppercase tracking-wider text-slate-400 group-hover:text-red-400">
                Slot {index + 1}
              </span>
            </button>
          ) : (
            <div
              key={index}
              className="flex min-h-24 items-center justify-center rounded-xl border border-dashed border-mint/50 bg-mint/5 text-sm font-bold text-mint"
            >
              + Карта
            </div>
          );
        })}
      </div>

      <div className="mt-5 space-y-4">
        <div>
          <p className="mb-2 text-[10px] font-bold uppercase tracking-[0.2em] text-white/40">Ранг</p>
          <div className="grid grid-cols-7 gap-1.5 sm:grid-cols-13">
            {ranks.map((rank) => {
              const isDisabled = suits.every(({ code }) => unavailableCards.has(`${rank}${code}`));
              return (
                <button
                  key={rank}
                  type="button"
                  disabled={isDisabled || flopCards.length >= 3}
                  onClick={() => setSelectedRank(rank)}
                  className={`rounded-lg py-2 text-sm font-black transition disabled:cursor-not-allowed disabled:opacity-20 ${
                    selectedRank === rank
                      ? 'bg-amber-400 text-amber-950 shadow-md shadow-amber-950/30'
                      : 'bg-white/[0.06] text-white/70 hover:bg-white/10'
                  }`}
                >
                  {rank}
                </button>
              );
            })}
          </div>
        </div>

        <div>
          <p className="mb-2 text-[10px] font-bold uppercase tracking-[0.2em] text-white/40">Масть для {selectedRank}</p>
          <div className="grid grid-cols-4 gap-2">
            {suits.map(({ code, symbol, label, color }) => (
              <button
                key={code}
                type="button"
                disabled={flopCards.length >= 3 || unavailableCards.has(`${selectedRank}${code}`)}
                onClick={() => selectSuit(code)}
                className="rounded-xl border border-white/10 bg-stone-50 px-2 py-3 text-sm font-black text-slate-700 transition hover:-translate-y-0.5 hover:bg-white disabled:cursor-not-allowed disabled:opacity-25"
                aria-label={`${selectedRank}, ${label}`}
              >
                <span className={`mr-1 text-xl ${color}`}>{symbol}</span> {code}
              </button>
            ))}
          </div>
        </div>
      </div>

      <button
        type="button"
        disabled={flopCards.length === 0}
        onClick={() => onFlopChange([])}
        className="mt-5 w-full rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2.5 text-sm font-bold text-white/60 transition hover:border-red-300/30 hover:bg-red-400/10 hover:text-red-200 disabled:cursor-not-allowed disabled:opacity-30"
      >
        🧹 Сбросить флоп
      </button>
    </section>
  );
}
