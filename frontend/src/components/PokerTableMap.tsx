export interface PokerTableMapProps {
  tableSize: number;
  btnPosition: number;
  heroSeat: number;
  heroPositionLabel: string;
}

export function PokerTableMap({
  tableSize,
  btnPosition,
  heroSeat,
  heroPositionLabel,
}: PokerTableMapProps) {
  // Rotate the layout so Hero always occupies the bottom-center seat.
  const seats = Array.from({ length: tableSize }, (_, index) => {
    const seat = index + 1;
    const angle =
      Math.PI / 2 + ((seat - heroSeat) * Math.PI * 2) / tableSize;

    const seatLeft = 50 + Math.cos(angle) * 45;
    const seatTop = 50 + Math.sin(angle) * 42;

    // Keep the dealer chip inside the felt, toward the table center.
    const btnLeft = 50 + Math.cos(angle) * 32;
    const btnTop = 50 + Math.sin(angle) * 28;

    return { seat, seatLeft, seatTop, btnLeft, btnTop };
  });

  return (
    <div className="relative mx-auto my-4 w-full max-w-[420px] px-4">
      <div className="bg-emerald-900 border-4 border-amber-900/80 rounded-[60px] aspect-[2.1/1] relative w-full flex items-center justify-center shadow-2xl shadow-emerald-950/50">
        <div className="z-0 rounded-full border border-emerald-400/30 bg-black/40 px-3.5 py-1.5 text-xs font-black tracking-wider text-emerald-300 shadow-inner backdrop-blur-sm">
          HERO = {heroPositionLabel}
        </div>

        {seats.map(({ seat, seatLeft, seatTop, btnLeft, btnTop }) => {
          const isHero = seat === heroSeat;
          const isButton = seat === btnPosition;

          return (
            <div key={seat}>
              {isButton && (
                <div
                  className="pointer-events-none absolute z-20 -translate-x-1/2 -translate-y-1/2 transition-all duration-300"
                  style={{ left: `${btnLeft}%`, top: `${btnTop}%` }}
                >
                  <span className="whitespace-nowrap rounded-full border border-amber-300 bg-amber-500 px-1.5 py-0.5 text-[9px] font-black text-amber-950 shadow-md">
                    🔘 BTN
                  </span>
                </div>
              )}

              <div
                className="absolute z-10 flex -translate-x-1/2 -translate-y-1/2 flex-col items-center transition-all duration-300"
                style={{ left: `${seatLeft}%`, top: `${seatTop}%` }}
              >
                <div
                  className={`flex h-9 w-9 items-center justify-center rounded-full text-xs shadow-md transition-transform ${
                    isHero
                      ? 'scale-110 border-2 border-emerald-300 bg-emerald-600 font-black text-white ring-2 ring-emerald-400/50'
                      : 'border border-slate-700 bg-slate-800/90 text-slate-300'
                  }`}
                  aria-label={isHero ? `Место ${seat}, Hero` : `Место ${seat}`}
                >
                  {isHero ? 'H' : seat}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
