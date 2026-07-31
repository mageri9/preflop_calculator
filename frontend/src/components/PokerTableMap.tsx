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
  const seats = Array.from({ length: tableSize }, (_, index) => {
    const seat = index + 1;
    const angle = Math.PI / 2 + ((seat - heroSeat) * Math.PI * 2) / tableSize;

    return {
      seat,
      seatLeft: 50 + Math.cos(angle) * 46,
      seatTop: 50 + Math.sin(angle) * 43,
      btnLeft: 50 + Math.cos(angle) * 32,
      btnTop: 50 + Math.sin(angle) * 29,
    };
  });

  return (
    <div className="relative mx-auto my-1 w-full max-w-[340px] px-2">
      <div className="relative flex aspect-[2.4/1] w-full items-center justify-center rounded-[40px] border-2 border-emerald-500/40 bg-slate-900 shadow-lg">
        <span className="font-mono text-xs font-bold tracking-wider text-emerald-400">
          {heroPositionLabel.toLowerCase()}
        </span>

        {seats.map(({ seat, seatLeft, seatTop, btnLeft, btnTop }) => {
          const isHero = seat === heroSeat;
          const isButton = seat === btnPosition;

          return (
            <div key={seat}>
              {isButton && (
                <span
                  className="pointer-events-none absolute z-20 -translate-x-1/2 -translate-y-1/2 rounded-full bg-amber-400 px-1 font-mono text-[8px] font-bold text-black"
                  style={{ left: `${btnLeft}%`, top: `${btnTop}%` }}
                >
                  btn
                </span>
              )}
              <div
                className={`absolute z-10 flex h-8 w-8 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full text-xs ${
                  isHero
                    ? 'scale-105 bg-emerald-600 font-bold text-white ring-2 ring-emerald-400'
                    : 'border border-slate-700/60 bg-slate-800 text-slate-400'
                }`}
                style={{ left: `${seatLeft}%`, top: `${seatTop}%` }}
                aria-label={isHero ? `Место ${seat}, Хиро` : `Место ${seat}`}
              >
                {seat}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
