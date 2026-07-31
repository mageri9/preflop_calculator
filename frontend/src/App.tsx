import { useEffect, useRef, useState } from 'react';
import { apiClient } from './api/client';
import { FlopPicker } from './components/FlopPicker';
import { Matrix13x13 } from './components/Matrix13x13';
import { PokerTableMap } from './components/PokerTableMap';
import { PostflopView } from './components/PostflopView';
import { TableControls } from './components/TableControls';
import { usePokerSession } from './hooks/usePokerSession';
import type { DecisionResult } from './types/poker';

type ActiveTab = 'preflop' | 'postflop';
type PotType = 'SRP' | '3BP';
type HeroRole = 'PFR' | 'PFC';
type HeroPosition = 'IP' | 'OOP';
type FacingAction = 'OPEN_2.5X' | 'LIMP' | 'PUSH';

export default function App() {
  const { session, loading, error, triggerNextHand, updateTableSize, updateSession } = usePokerSession();
  const [activeTab, setActiveTab] = useState<ActiveTab>('preflop');
  const [selectedCombo, setSelectedCombo] = useState<string>();
  const [decisionResult, setDecisionResult] = useState<DecisionResult | null>(null);
  const [decisionLoading, setDecisionLoading] = useState(false);
  const [decisionError, setDecisionError] = useState<string>();
  const [facingAction, setFacingAction] = useState<FacingAction>('OPEN_2.5X');
  const [flopCards, setFlopCards] = useState<string[]>([]);
  const [postflopResult, setPostflopResult] = useState<DecisionResult | null>(null);
  const [postflopLoading, setPostflopLoading] = useState(false);
  const [postflopError, setPostflopError] = useState<string>();
  const [potType, setPotType] = useState<PotType>('SRP');
  const [heroRole, setHeroRole] = useState<HeroRole>('PFR');
  const [heroPosition, setHeroPosition] = useState<HeroPosition>('IP');
  const preflopRequestId = useRef(0);
  const postflopRequestId = useRef(0);
  const isTelegram = Boolean(window.Telegram?.WebApp?.initData);

  const handleSelectCombo = async (combo: string, action = facingAction) => {
    const requestId = ++preflopRequestId.current;
    setSelectedCombo(combo);
    setDecisionLoading(true);
    setDecisionError(undefined);

    try {
      const result = await apiClient.getPreflopDecision({ hero_combo: combo, facing_action: action });
      if (requestId === preflopRequestId.current) setDecisionResult(result);
    } catch (requestError) {
      if (requestId === preflopRequestId.current) {
        setDecisionError(requestError instanceof Error ? requestError.message : 'Не удалось получить решение');
      }
    } finally {
      if (requestId === preflopRequestId.current) setDecisionLoading(false);
    }
  };

  useEffect(() => {
    const webApp = window.Telegram?.WebApp;
    webApp?.ready();
    webApp?.expand();
  }, []);

  useEffect(() => {
    if (flopCards.length !== 3 || !selectedCombo) {
      postflopRequestId.current += 1;
      setPostflopResult(null);
      setPostflopLoading(false);
      return;
    }

    const requestId = ++postflopRequestId.current;
    setPostflopLoading(true);
    setPostflopError(undefined);

    void apiClient
      .getPostflopDecision({
        hero_cards: selectedCombo,
        flop_cards: flopCards,
        pot_type: potType,
        hero_role: heroRole,
        hero_position: heroPosition,
      })
      .then((result) => {
        if (requestId === postflopRequestId.current) setPostflopResult(result);
      })
      .catch((requestError: unknown) => {
        if (requestId === postflopRequestId.current) {
          setPostflopResult(null);
          setPostflopError(requestError instanceof Error ? requestError.message : 'Не удалось получить postflop-решение');
        }
      })
      .finally(() => {
        if (requestId === postflopRequestId.current) setPostflopLoading(false);
      });
  }, [flopCards, selectedCombo, potType, heroRole, heroPosition]);

  const tableControls = session ? (
    <TableControls
      session={session}
      onNextHand={() => void triggerNextHand()}
      onChangeTableSize={(size) => void updateTableSize(size)}
      onUpdateSession={(payload) => void updateSession(payload)}
      isLoading={loading}
    />
  ) : (
    <div className="py-12 text-center text-white/50">Загрузка сессии…</div>
  );

  return (
    <main className="min-h-screen px-3 py-6 sm:px-5 sm:py-8">
      <section className="mx-auto w-full max-w-2xl animate-rise overflow-hidden rounded-[2rem] border border-white/10 bg-ink/90 shadow-card backdrop-blur">
        <header className="relative overflow-hidden border-b border-white/10 px-6 pb-6 pt-8">
          <div className="absolute -right-8 -top-16 h-44 w-44 rounded-full bg-mint/10 blur-2xl" />
          <div className={`mb-5 inline-flex rounded-full px-3 py-1 text-xs font-bold uppercase tracking-[0.16em] ${isTelegram ? 'bg-mint/15 text-mint' : 'bg-amber/15 text-amber'}`}>
            {isTelegram ? 'Telegram Mini App' : 'Dev Mode (браузер)'}
          </div>
          <p className="text-sm uppercase tracking-[0.3em] text-white/40">Table assistant</p>
          <h1 className="mt-2 font-display text-4xl text-cream">Poker Calculator</h1>

          <div className="relative mt-6 grid grid-cols-2 rounded-xl border border-white/10 bg-black/20 p-1">
            {([
              ['preflop', 'Preflop'],
              ['postflop', 'Postflop'],
            ] as const).map(([tab, label]) => (
              <button
                key={tab}
                type="button"
                onClick={() => setActiveTab(tab)}
                className={`rounded-lg px-4 py-2.5 text-sm font-black transition ${activeTab === tab ? 'bg-amber-400 text-amber-950 shadow-lg' : 'text-white/50 hover:text-white'}`}
                aria-pressed={activeTab === tab}
              >
                {label}
              </button>
            ))}
          </div>
        </header>

        <div className="p-4 sm:p-6">
          {error && <div className="mb-5 rounded-2xl border border-red-400/20 bg-red-400/10 p-4 text-sm text-red-200">{error}</div>}

          {activeTab === 'preflop' ? (
            <div className="space-y-6">
              {session && (
                <PokerTableMap
                  tableSize={session.table_size}
                  btnPosition={session.btn_position}
                  heroSeat={session.hero_seat}
                  heroPositionLabel={session.hero_position_label}
                />
              )}
              {tableControls}

              <section>
                <div className="mb-3 flex items-end justify-between">
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-white/40">Пресеты действий</p>
                    <h2 className="font-display text-2xl text-cream">Стартовые руки</h2>
                  </div>
                  {selectedCombo && <span className="rounded-lg bg-amber-400 px-2.5 py-1 text-sm font-black text-amber-950">{selectedCombo}</span>}
                </div>
                <div className="mb-4 grid grid-cols-3 gap-2">
                  {([
                    ['OPEN_2.5X', 'Open 2.5x'],
                    ['LIMP', 'Limp'],
                    ['PUSH', 'Push'],
                  ] as const).map(([action, label]) => (
                    <button
                      key={action}
                      type="button"
                      disabled={decisionLoading}
                      onClick={() => {
                        setFacingAction(action);
                        if (selectedCombo) void handleSelectCombo(selectedCombo, action);
                      }}
                      className={`rounded-lg px-2 py-2 text-xs font-black uppercase transition disabled:opacity-50 ${
                        facingAction === action
                          ? 'bg-emerald-400 text-emerald-950'
                          : 'bg-white/[0.06] text-white/60 hover:bg-white/10'
                      }`}
                      aria-pressed={facingAction === action}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                <Matrix13x13
                  activeRangeStr={decisionResult?.range_str}
                  selectedCombo={selectedCombo}
                  onSelectCombo={(combo) => void handleSelectCombo(combo)}
                  isLoading={decisionLoading}
                />
              </section>

              {decisionError && <div className="rounded-2xl border border-red-400/20 bg-red-400/10 p-4 text-sm text-red-200">{decisionError}</div>}
              {decisionResult && (
                <div className="flex items-center justify-between rounded-2xl border border-amber-300/20 bg-amber-400/10 p-4">
                  <div>
                    <p className="text-xs uppercase tracking-wider text-white/40">Рекомендация</p>
                    <p className="mt-1 text-xl font-extrabold text-amber-300">{decisionResult.action}</p>
                  </div>
                  <p className="text-right text-sm text-cream">
                    <span className="block font-bold">{selectedCombo}</span>
                    <span className="text-white/50">{decisionResult.range_stats?.percentage ?? 0}% диапазона</span>
                  </p>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-6">
              {tableControls}
              {!selectedCombo && (
                <div className="rounded-2xl border border-amber-300/20 bg-amber-400/10 p-4 text-sm text-amber-100">
                  Сначала выберите руку Хиро во вкладке Preflop.
                </div>
              )}
              <FlopPicker flopCards={flopCards} onFlopChange={setFlopCards} heroCombo={selectedCombo} />
              {postflopError && <div className="rounded-2xl border border-red-400/20 bg-red-400/10 p-4 text-sm text-red-200">{postflopError}</div>}
              <PostflopView
                result={postflopResult}
                potType={potType}
                heroRole={heroRole}
                heroPosition={heroPosition}
                onUpdateContext={(payload) => {
                  if (payload.potType) setPotType(payload.potType);
                  if (payload.heroRole) setHeroRole(payload.heroRole);
                  if (payload.heroPosition) setHeroPosition(payload.heroPosition);
                }}
                isLoading={postflopLoading}
              />
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
