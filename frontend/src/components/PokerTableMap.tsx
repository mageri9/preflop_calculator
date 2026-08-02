export interface PokerTableMapProps {
  tableSize: number;
  btnPosition: number;
  heroSeat: number;
  heroPositionLabel: string;
  onSeatClick?: (position: string) => void;
  seatActions?: Record<string, string>;
  invalidPositions?: string[];
}

const POSITION_MAP: Record<number, string[]> = {
  9: ['BTN', 'SB', 'BB', 'UTG', 'UTG+1', 'MP', 'MP+1', 'HJ', 'CO'],
  8: ['BTN', 'SB', 'BB', 'UTG', 'MP', 'MP+1', 'HJ', 'CO'],
  7: ['BTN', 'SB', 'BB', 'UTG', 'MP', 'HJ', 'CO'],
  6: ['BTN', 'SB', 'BB', 'UTG', 'HJ', 'CO'],
  5: ['BTN', 'SB', 'BB', 'UTG', 'CO'],
  4: ['BTN', 'SB', 'BB', 'CO'],
  3: ['BTN', 'SB', 'BB'],
  2: ['BTN/SB', 'BB'],
};

// Сетка координат прижатая к углам и вертикальным столбикам по краям
const SEAT_LAYOUTS: Record<number, Array<{ left: number; top: number }>> = {
  9: [
    { left: 50, top: 90 }, // 0: Hero (Снизу по центру)
    { left: 88, top: 83 }, // 1: Столбик справа - нижний угол
    { left: 92, top: 50 }, // 2: Столбик справа - центр
    { left: 88, top: 17 }, // 3: Столбик справа - верхний угол
    { left: 63, top: 10 }, // 4: Вверху справа
    { left: 37, top: 10 }, // 5: Вверху слева (напротив)
    { left: 12, top: 17 }, // 6: Столбик слева - верхний угол
    { left: 8, top: 50 },  // 7: Столбик слева - центр
    { left: 12, top: 83 }, // 8: Столбик слева - нижний угол
  ],
  8: [
    { left: 50, top: 90 }, // 0: Hero
    { left: 88, top: 83 }, // 1: Столбик справа - нижний угол
    { left: 92, top: 50 }, // 2: Столбик справа - центр
    { left: 88, top: 17 }, // 3: Столбик справа - верхний угол
    { left: 50, top: 10 }, // 4: Вверху по центру (напротив)
    { left: 12, top: 17 }, // 5: Столбик слева - верхний угол
    { left: 8, top: 50 },  // 6: Столбик слева - центр
    { left: 12, top: 83 }, // 7: Столбик слева - нижний угол
  ],
  7: [
    { left: 50, top: 90 },
    { left: 88, top: 81 },
    { left: 92, top: 48 },
    { left: 82, top: 14 },
    { left: 18, top: 14 },
    { left: 8, top: 48 },
    { left: 12, top: 81 },
  ],
  6: [
    { left: 50, top: 90 },
    { left: 88, top: 80 },
    { left: 88, top: 20 },
    { left: 50, top: 10 },
    { left: 12, top: 20 },
    { left: 12, top: 80 },
  ],
  5: [
    { left: 50, top: 90 },
    { left: 90, top: 60 },
    { left: 70, top: 14 },
    { left: 30, top: 14 },
    { left: 10, top: 60 },
  ],
  4: [
    { left: 50, top: 90 },
    { left: 90, top: 50 },
    { left: 50, top: 10 },
    { left: 10, top: 50 },
  ],
  3: [
    { left: 50, top: 90 },
    { left: 80, top: 18 },
    { left: 20, top: 18 },
  ],
  2: [
    { left: 50, top: 90 },
    { left: 50, top: 10 },
  ],
};

function getPositionLabel(seat: number, btnPosition: number, tableSize: number): string {
  const seatIndex = (seat - btnPosition + tableSize) % tableSize;
  const labels = POSITION_MAP[tableSize] || POSITION_MAP[6];
  return labels[seatIndex] || `S${seat}`;
}

export function PokerTableMap({
  tableSize,
  btnPosition,
  heroSeat,
  heroPositionLabel,
  onSeatClick,
  seatActions = {},
  invalidPositions = [],
}: PokerTableMapProps) {
  const layout = SEAT_LAYOUTS[tableSize] || SEAT_LAYOUTS[9];

  const seats = Array.from({ length: tableSize }, (_, index) => {
    const seat = index + 1;
    const offset = (seat - heroSeat + tableSize) % tableSize;
    const pos = layout[offset] || { left: 50, top: 50 };

    const posLabel = getPositionLabel(seat, btnPosition, tableSize);

    return {
      seat,
      posLabel,
      seatLeft: pos.left,
      seatTop: pos.top,
      chipLeft: pos.left + (50 - pos.left) * 0.35,
      chipTop: pos.top + (50 - pos.top) * 0.35,
    };
  });

  return (
    <div className="relative mx-auto my-2 w-full max-w-[380px] px-2 select-none">
      {/* Внешний кожаный борт стола */}
      <div className="relative flex aspect-[2.1/1] w-full items-center justify-center rounded-[50px] border-[5px] border-[#2b180d] bg-[#1a0e08] p-2 shadow-[0_12px_30px_rgba(0,0,0,0.9)] ring-1 ring-amber-950/60">

        {/* Изумрудное покерное сукно */}
        <div className="relative flex h-full w-full items-center justify-center rounded-[40px] border border-amber-400/30 bg-[radial-gradient(ellipse_at_center,_#0f4838_0%,_#07281f_65%,_#03140f_100%)] shadow-[inset_0_4px_25px_rgba(0,0,0,0.85)]">

          {/* Водяной знак в центре стола */}
          <div className="pointer-events-none flex flex-col items-center opacity-25">
            <span className="text-xs tracking-[0.3em] text-emerald-300">♠ ♥ ♦ ♣</span>
            <span className="mt-0.5 font-mono text-[8px] font-extrabold uppercase tracking-widest text-emerald-200">
              {heroPositionLabel}
            </span>
          </div>

          {/* Места игроков, баттон и блайнды */}
          {seats.map(({ seat, posLabel, seatLeft, seatTop, chipLeft, chipTop }) => {
            const isHero = seat === heroSeat;
            const isButton = seat === btnPosition;
            const isSB = posLabel === 'SB' || posLabel === 'BTN/SB';
            const isBB = posLabel === 'BB';
            const seatAction = seatActions[posLabel];
            const actionClass = invalidPositions.includes(posLabel)
              ? 'ring-2 ring-red-500 bg-red-950 text-red-200'
              : seatAction === 'LIMP' ? 'ring-2 ring-blue-400 bg-blue-900 text-blue-100'
              : seatAction === 'OPEN' ? 'ring-2 ring-amber-400 bg-amber-900 text-amber-100'
              : seatAction === 'THREE_BET' ? 'ring-2 ring-red-500 bg-red-900 text-red-100'
              : seatAction === 'PUSH' ? 'ring-2 ring-rose-700 bg-rose-950 text-rose-100' : '';

            return (
              <div key={seat}>
                {/* 3D Фишка Дилера (BTN) */}
                {isButton && (
                  <div
                    className="pointer-events-none absolute z-20 flex h-5 w-5 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-amber-200 bg-gradient-to-b from-white via-slate-100 to-slate-300 font-mono text-[8px] font-black text-slate-950 shadow-[0_3px_6px_rgba(0,0,0,0.7)] ring-1 ring-black/40"
                    style={{ left: `${chipLeft}%`, top: `${chipTop}%` }}
                    title="Dealer Button"
                  >
                    D
                  </div>
                )}

                {/* Фишка Малого Блайнда (SB) */}
                {isSB && tableSize > 2 && !isButton && (
                  <div
                    className="pointer-events-none absolute z-20 flex h-4 w-4 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-purple-300 bg-gradient-to-b from-purple-500 to-purple-800 font-mono text-[7px] font-extrabold text-white shadow-[0_2px_4px_rgba(0,0,0,0.6)] ring-1 ring-black/30"
                    style={{ left: `${chipLeft}%`, top: `${chipTop}%` }}
                    title="Small Blind"
                  >
                    SB
                  </div>
                )}

                {/* Фишка Большого Блайнда (BB) */}
                {isBB && (
                  <div
                    className="pointer-events-none absolute z-20 flex h-4 w-4 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-amber-300 bg-gradient-to-b from-amber-400 to-amber-700 font-mono text-[7px] font-extrabold text-slate-950 shadow-[0_2px_4px_rgba(0,0,0,0.6)] ring-1 ring-black/30"
                    style={{ left: `${chipLeft}%`, top: `${chipTop}%` }}
                    title="Big Blind"
                  >
                    BB
                  </div>
                )}

                {/* Аватарка с позицией прямо внутри круга */}
                <div
                  className="absolute z-10 flex -translate-x-1/2 -translate-y-1/2 flex-col items-center justify-center"
                  style={{ left: `${seatLeft}%`, top: `${seatTop}%` }}
                >
                  <button
                    type="button"
                    disabled={isHero || !onSeatClick}
                    onClick={() => onSeatClick?.(posLabel)}
                    title={seatAction ?? (isHero ? 'Hero' : 'Click to set action')}
                    className={`relative flex h-8 w-8 items-center justify-center rounded-full font-mono text-[8.5px] font-black shadow-md transition-all ${
                      isHero
                        ? 'bg-gradient-to-b from-emerald-500 via-emerald-600 to-emerald-950 text-white ring-2 ring-amber-300 shadow-[0_0_12px_rgba(52,211,153,0.6)] scale-110'
                        : 'border border-slate-700/80 bg-gradient-to-b from-slate-800 to-slate-950 text-amber-300/90'
                    } ${actionClass}`}
                  >
                    <span className="truncate px-0.5">{posLabel}</span>

                    {/* Плашка YOU над Хиро */}
                    {isHero && (
                      <span className="absolute -top-1.5 rounded-full bg-amber-400 px-1 py-[0.5px] font-mono text-[6px] font-black text-black shadow">
                        YOU
                      </span>
                    )}
                    {!isHero && seatAction && <span className="absolute -bottom-2 rounded bg-slate-950 px-1 text-[6px] text-white">{seatAction}</span>}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
