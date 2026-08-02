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
type FacingAction = 'FIRST_IN' | 'OPEN_2.5X' | 'LIMP' | 'PUSH';

export default function App() {
  const { session, loading, error, triggerNextHand, updateTableSize, updateSession } = usePokerSession();
  const [activeTab, setActiveTab] = useState<ActiveTab>('preflop');
  const [selectedCombo, setSelectedCombo] = useState<string>();
  const [decisionResult, setDecisionResult] = useState<DecisionResult | null>(null);
  const [decisionLoading, setDecisionLoading] = useState(false);
  const [decisionError, setDecisionError] = useState<string>();
  const [facingAction, setFacingAction] = useState<FacingAction>('FIRST_IN');
  const [flopCards, setFlopCards] = useState<string[]>([]);
  const [postflopResult, setPostflopResult] = useState<DecisionResult | null>(null);
  const [postflopLoading, setPostflopLoading] = useState(false);
  const [postflopError, setPostflopError] = useState<string>();
  const [potType, setPotType] = useState<PotType>('SRP');
  const [heroRole, setHeroRole] = useState<HeroRole>('PFR');
  const [heroPosition, setHeroPosition] = useState<HeroPosition>('IP');
  const preflopRequestId = useRef(0);
  const postflopRequestId = useRef(0);

  useEffect(() => {
    window.Telegram?.WebApp?.ready();
    window.Telegram?.WebApp?.expand();
  }, []);

  // Автоматическая загрузка актуального диапазона префлопа при смене позиции / ситуации / стека
  useEffect(() => {
    if (!session) return;

    const requestId = ++preflopRequestId.current;
    setDecisionLoading(true);
    setDecisionError(undefined);

    apiClient.getPreflopDecision({
      hero_combo: selectedCombo,
      facing_action: facingAction === 'FIRST_IN' ? undefined : facingAction,
    })
      .then((result) => {
        if (requestId === preflopRequestId.current) setDecisionResult(result);
      })
      .catch((requestError: unknown) => {
        if (requestId === preflopRequestId.current) {
          setDecisionError(requestError instanceof Error ? requestError.message : 'Не удалось получить диапазон');
        }
      })
      .finally(() => {
        if (requestId === preflopRequestId.current) setDecisionLoading(false);
      });
  }, [
    session?.hero_position_label,
    session?.table_size,
    session?.stack_bb,
    session?.icm_stage,
    session?.has_ante,
    session?.opponent_style,
    facingAction,
    selectedCombo,
  ]);

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
    void apiClient.getPostflopDecision({
      hero_cards: selectedCombo,
      flop_cards: flopCards,
      pot_type: potType,
      hero_role: heroRole,
      hero_position: heroPosition,
    }).then((result) => {
      if (requestId === postflopRequestId.current) setPostflopResult(result);
    }).catch((requestError: unknown) => {
      if (requestId === postflopRequestId.current) {
        setPostflopResult(null);
        setPostflopError(requestError instanceof Error ? requestError.message : 'Не удалось получить постфлоп-решение');
      }
    }).finally(() => {
      if (requestId === postflopRequestId.current) setPostflopLoading(false);
    });
  }, [flopCards, selectedCombo, potType, heroRole, heroPosition]);

  const handleSelectCombo = (combo: string) => {
    // Если нажимаем на уже выбранную руку — снимаем выбор
    setSelectedCombo((prev) => (prev === combo ? undefined : combo));
  };

  const handleNextHand = () => {
    setSelectedCombo(undefined);
    void triggerNextHand();
  };

  const handleFacingActionChange = (action: FacingAction) => {
    setFacingAction(action);
    setSelectedCombo(undefined);
  };

  const table = session && (
    <PokerTableMap
      tableSize={session.table_size}
      btnPosition={session.btn_position}
      heroSeat={session.hero_seat}
      heroPositionLabel={session.hero_position_label}
    />
  );

  return (
    <main className="flex h-screen max-h-screen flex-col justify-between overflow-hidden bg-slate-950 p-2 font-sans text-slate-100">
      <header className="mx-auto grid w-full max-w-[360px] grid-cols-2 rounded-lg bg-slate-900 p-1">
        {([['preflop', 'ПРЕФЛОП'], ['postflop', 'ПОСТФЛОП']] as const).map(([tab, label]) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={`rounded-md py-1.5 text-[11px] font-bold tracking-wider transition ${activeTab === tab ? 'bg-amber-400 text-black' : 'text-slate-500 hover:text-slate-200'}`}
            aria-pressed={activeTab === tab}
          >
            {label}
          </button>
        ))}
      </header>

      <div className="mx-auto flex min-h-0 w-full max-w-md flex-1 flex-col justify-center gap-1 overflow-hidden py-1">
        {error && <div className="rounded-lg bg-red-950/60 p-2 text-xs text-red-300">{error}</div>}

        {activeTab === 'preflop' ? (
          <div className="flex min-h-0 flex-col gap-1">
            {table}
            {session && (
              <TableControls
                session={session}
                onNextHand={handleNextHand}
                onChangeTableSize={(size) => {
                  setSelectedCombo(undefined);
                  void updateTableSize(size);
                }}
                onUpdateSession={(payload) => {
                  setSelectedCombo(undefined);
                  void updateSession(payload);
                }}
                isLoading={loading}
              />
            )}
            <Matrix13x13
              activeRangeStr={decisionResult?.range_str}
              selectedCombo={selectedCombo}
              onSelectCombo={handleSelectCombo}
              isLoading={decisionLoading}
            />
            <label className="mx-auto flex w-full max-w-[360px] items-center gap-2 rounded-lg border border-slate-800 bg-slate-900/70 px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">
              Ситуация
              <select
                value={facingAction}
                onChange={(event) => handleFacingActionChange(event.target.value as FacingAction)}
                className="ml-auto rounded-md bg-slate-800 px-2 py-1 text-xs normal-case text-slate-200"
              >
                <option value="FIRST_IN">Первое слово / Open</option>
                <option value="OPEN_2.5X">Против Open 2.5x</option>
                <option value="LIMP">Против Limp</option>
                <option value="PUSH">Против Push</option>
              </select>
            </label>
            {decisionError && <div className="rounded-lg bg-red-950/60 p-2 text-xs text-red-300">{decisionError}</div>}
            <div className="mx-auto flex w-full max-w-[360px] items-center justify-between rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs font-bold text-amber-300">
              <span>
                {decisionLoading
                  ? 'ЗАГРУЗКА...'
                  : decisionResult
                    ? selectedCombo
                      ? `РУКА ${selectedCombo}: ${decisionResult.action} (${decisionResult.range_stats?.percentage ?? 0}% рук)`
                      : `ДИАПАЗОН ${session?.hero_position_label ?? ''}: ${decisionResult.action} (${decisionResult.range_stats?.percentage ?? 0}% рук)`
                    : 'ДИАПАЗОН: —'}
              </span>
              {decisionResult && selectedCombo && !['FOLD', 'PUSH'].includes(decisionResult.action) && (
                <button type="button" onClick={() => setActiveTab('postflop')} className="rounded-md bg-amber-400 px-2 py-1 text-[10px] text-black">К флопу</button>
              )}
            </div>
          </div>
        ) : (
          <div className="flex min-h-0 flex-col gap-2 overflow-auto">
            {table}
            {!postflopResult && <FlopPicker flopCards={flopCards} onFlopChange={setFlopCards} />}
            {postflopError && <div className="rounded-lg bg-red-950/60 p-2 text-xs text-red-300">{postflopError}</div>}
            <PostflopView
              result={postflopResult}
              flopCards={flopCards}
              heroCombo={selectedCombo}
              stackBB={session?.stack_bb ?? 0}
              potType={potType}
              heroRole={heroRole}
              heroPosition={heroPosition}
              onUpdateContext={(payload) => {
                if (payload.potType) setPotType(payload.potType);
                if (payload.heroRole) setHeroRole(payload.heroRole);
                if (payload.heroPosition) setHeroPosition(payload.heroPosition);
              }}
              isLoading={postflopLoading}
              onEditFlop={() => {
                setPostflopResult(null);
                setFlopCards([]);
              }}
              onNextHand={() => {
                setFlopCards([]);
                setPostflopResult(null);
                setSelectedCombo(undefined);
                setDecisionResult(null);
                setActiveTab('preflop');
                void triggerNextHand();
              }}
            />
          </div>
        )}
      </div>
    </main>
  );
}