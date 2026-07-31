import { useEffect } from 'react';
import { usePokerSession } from './hooks/usePokerSession';

const sessionFields = [
  ['Позиция Хиро', 'hero_position_label'],
  ['Стек', 'stack_bb'],
  ['Размер стола', 'table_size'],
  ['Уровень блайндов', 'blind_level'],
] as const;

export default function App() {
  const { session, loading, error, triggerNextHand } = usePokerSession();
  const isTelegram = Boolean(window.Telegram?.WebApp?.initData);

  useEffect(() => {
    const webApp = window.Telegram?.WebApp;
    webApp?.ready();
    webApp?.expand();
  }, []);

  return (
    <main className="min-h-screen px-5 py-8 sm:grid sm:place-items-center">
      <section className="mx-auto w-full max-w-lg animate-rise overflow-hidden rounded-[2rem] border border-white/10 bg-ink/90 shadow-card backdrop-blur">
        <header className="relative overflow-hidden border-b border-white/10 px-6 pb-7 pt-8">
          <div className="absolute -right-8 -top-16 h-44 w-44 rounded-full bg-mint/10 blur-2xl" />
          <div
            className={`mb-5 inline-flex rounded-full px-3 py-1 text-xs font-bold uppercase tracking-[0.16em] ${
              isTelegram
                ? 'bg-mint/15 text-mint'
                : 'bg-amber/15 text-amber'
            }`}
          >
            {isTelegram ? 'Telegram Mini App' : 'Dev Mode (Браузер)'}
          </div>
          <p className="text-sm uppercase tracking-[0.3em] text-white/40">
            Table assistant
          </p>
          <h1 className="mt-2 font-display text-4xl text-cream">
            Preflop Calculator
          </h1>
        </header>

        <div className="p-6">
          {error && (
            <div className="mb-5 rounded-2xl border border-red-400/20 bg-red-400/10 p-4 text-sm text-red-200">
              {error}
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            {sessionFields.map(([label, key]) => (
              <article
                key={key}
                className="rounded-2xl border border-white/10 bg-white/[0.04] p-4"
              >
                <p className="text-xs uppercase tracking-wider text-white/40">
                  {label}
                </p>
                <p className="mt-2 text-2xl font-semibold text-cream">
                  {session
                    ? `${session[key]}${key === 'stack_bb' ? ' BB' : ''}`
                    : '—'}
                </p>
              </article>
            ))}
          </div>

          <button
            type="button"
            disabled={loading}
            onClick={() => void triggerNextHand()}
            className="mt-6 w-full rounded-2xl bg-mint px-5 py-4 font-bold text-ink transition hover:bg-cream disabled:cursor-wait disabled:opacity-60"
          >
            {loading ? 'Загрузка…' : 'Следующая раздача'}
          </button>
        </div>
      </section>
    </main>
  );
}
