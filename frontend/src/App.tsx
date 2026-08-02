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

const getActionColorClass = (act: string, pct: number) => {
  if (pct === 0) {
    return 'border border-slate-800/50 bg-slate-900/40 text-slate-600 opacity-40';
  }

  switch (act) {
    case 'PUSH':
    case '3BET_PUSH':
      return 'border border-rose-500 bg-rose-500/30 text-rose-300'; // КРАСНЫЙ ДЛЯ ПУША
    case 'OPEN_RAISE':
    case 'RAISE':
    case '3BET_RAISE':
    case 'BET':
      return 'border border-emerald-400 bg-emerald-500/20 text-emerald-300';
    case 'ISOLATE':
      return 'border border-blue-400 bg-blue-500/25 text-blue-300'; // СИНИЙ ДЛЯ ИЗОЛЕЙТА
    case 'CALL':
    case 'DEFEND':
      return 'border border-amber-400 bg-amber-500/20 text-amber-300';
    case 'CHECK':
      return 'border border-cyan-400 bg-cyan-500/20 text-cyan-300';
    case 'FOLD':
      return 'border border-stone-700/60 bg-stone-800/60 text-stone-500 opacity-60'; // ТУСКЛЫЙ "ФУФЛЫЖНЫЙ" ФОЛД
    default:
      return 'border border-slate-700 bg-slate-800 text-slate-200';
  }
};

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

            <div className="mx-auto flex w-full max-w-[360px] flex-col gap-2 rounded-xl border border-amber-400/30 bg-slate-900 p-3 text-xs shadow-xl">
              <div className="flex items-center justify-between font-extrabold text-amber-300">
                <span>
                  {decisionLoading
                    ? 'ЗАГРУЗКА...'
                    : decisionResult
                      ? selectedCombo
                        ? `РУКА ${selectedCombo}: ${decisionResult.action}`
                        : `ПОЗИЦИЯ ${session?.hero_position_label ?? ''}: ${decisionResult.action}`
                      : 'РЕШЕНИЕ: —'}
                </span>
                {decisionResult?.equity_pct !== undefined && (
                  <span className="rounded-md bg-amber-400/20 px-2 py-0.5 text-amber-200">
                    Эквити: {decisionResult.equity_pct}%
                  </span>
                )}
              </div>

              {decisionResult?.frequencies && Object.keys(decisionResult.frequencies).length > 0 && (
                <div className="space-y-1">
                  <p className="text-[10px] font-black uppercase tracking-wider text-slate-400">
                    Варианты действий и частоты (%):
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(decisionResult.frequencies).map(([act, pct]) => {
                      const colorClass = getActionColorClass(act, pct);
                      return (
                        <div
                          key={act}
                          className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[10px] font-bold transition-colors ${colorClass}`}
                        >
                          <span>{act}</span>
                          <span className="font-mono font-black">{pct}%</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {decisionResult && selectedCombo && !['FOLD', 'PUSH'].includes(decisionResult.action) && (
                <button
                  type="button"
                  onClick={() => setActiveTab('postflop')}
                  className="mt-1 w-full rounded-md bg-amber-400 py-1.5 text-center text-xs font-bold text-black transition hover:bg-amber-300"
                >
                  Перейти к флопу
                </button>
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