import { useEffect, useRef, useState } from 'react';
import { apiClient } from './api/client';
import { Matrix13x13 } from './components/Matrix13x13';
import { usePokerSession } from './hooks/usePokerSession';
import type { DecisionResult } from './types/poker';

const sessionFields = [
  ['Позиция Хиро', 'hero_position_label'],
  ['Стек', 'stack_bb'],
  ['Размер стола', 'table_size'],
  ['Уровень блайндов', 'blind_level'],
] as const;

export default function App() {
  const { session, loading, error, triggerNextHand } = usePokerSession();
  const [selectedCombo, setSelectedCombo] = useState<string>();
  const [decisionResult, setDecisionResult] = useState<DecisionResult | null>(null);
  const [decisionLoading, setDecisionLoading] = useState(false);
  const [decisionError, setDecisionError] = useState<string>();
  const requestIdRef = useRef(0);
  const isTelegram = Boolean(window.Telegram?.WebApp?.initData);

  const handleSelectCombo = async (combo: string) => {
    const requestId = ++requestIdRef.current;
    setSelectedCombo(combo);
    setDecisionLoading(true);
    setDecisionError(undefined);

    try {
      const result = await apiClient.getPreflopDecision({ hero_combo: combo });
      if (requestId === requestIdRef.current) {
        setDecisionResult(result);
      }
    } catch (requestError) {
      if (requestId === requestIdRef.current) {
        setDecisionError(
          requestError instanceof Error ? requestError.message : 'Не удалось получить решение',
        );
      }
    } finally {
      if (requestId === requestIdRef.current) {
        setDecisionLoading(false);
      }
    }
  };

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

          <div className="mt-6">
            <Matrix13x13
              activeRangeStr={decisionResult?.range_str}
              selectedCombo={selectedCombo}
              onSelectCombo={(combo) => void handleSelectCombo(combo)}
              isLoading={decisionLoading}
            />
          </div>

          {decisionError && (
            <div className="mt-4 rounded-2xl border border-red-400/20 bg-red-400/10 p-4 text-sm text-red-200">
              {decisionError}
            </div>
          )}

          {decisionResult && (
            <div className="mt-4 flex items-center justify-between rounded-2xl border border-amber-300/20 bg-amber-400/10 p-4">
              <div>
                <p className="text-xs uppercase tracking-wider text-white/40">Рекомендация</p>
                <p className="mt-1 text-xl font-extrabold text-amber-300">
                  {decisionResult.action}
                </p>
              </div>
              <p className="text-right text-sm text-cream">
                <span className="block font-bold">{selectedCombo}</span>
                <span className="text-white/50">
                  {decisionResult.range_stats?.percentage ?? 0}% диапазона
                </span>
              </p>
            </div>
          )}

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
