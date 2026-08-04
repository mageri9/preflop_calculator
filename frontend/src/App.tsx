import { useEffect, useRef, useState } from 'react';
import { apiClient } from './api/client';
import { FlopPicker } from './components/FlopPicker';
import { Matrix13x13 } from './components/Matrix13x13';
import { PokerTableMap } from './components/PokerTableMap';
import { PostflopView } from './components/PostflopView';
import { TableControls } from './components/TableControls';
import { usePokerSession } from './hooks/usePokerSession';
import { useActionSequence } from './hooks/useActionSequence';
import type { DecisionResult, VillainPosition } from './types/poker';

type ActiveTab = 'preflop' | 'postflop';
type PotType = 'SRP' | '3BP';
type HeroRole = 'PFR' | 'PFC';
type HeroPosition = 'IP' | 'OOP';
type FacingAction = 'FIRST_IN' | 'OPEN_2.5X' | 'LIMP' | 'PUSH' | 'THREE_BET' | 'MULTIWAY';

const POSITIONS_BY_TABLE_SIZE: Record<number, VillainPosition[]> = {
  2: ['BTN/SB', 'BB'],
  3: ['BTN', 'SB', 'BB'],
  4: ['CO', 'BTN', 'SB', 'BB'],
  5: ['UTG', 'CO', 'BTN', 'SB', 'BB'],
  6: ['UTG', 'HJ', 'CO', 'BTN', 'SB', 'BB'],
  7: ['UTG', 'MP', 'HJ', 'CO', 'BTN', 'SB', 'BB'],
  8: ['UTG', 'MP', 'MP+1', 'HJ', 'CO', 'BTN', 'SB', 'BB'],
  9: ['UTG', 'UTG+1', 'MP', 'MP+1', 'HJ', 'CO', 'BTN', 'SB', 'BB'],
};

function availableVillainPositions(tableSize: number, heroPosition?: string): VillainPosition[] {
  const positions = POSITIONS_BY_TABLE_SIZE[tableSize] ?? POSITIONS_BY_TABLE_SIZE[9];
  const heroIndex = positions.indexOf(heroPosition as VillainPosition);
  return heroIndex > 0 ? positions.slice(0, heroIndex) : [];
}

function defaultVillainPosition(tableSize: number, heroPosition?: string): VillainPosition {
  const positions = availableVillainPositions(tableSize, heroPosition);
  return positions[positions.length - 1] ?? 'BTN';
}

const getActionColorClass = (act: string, pct: number) => {
  act = act.toUpperCase();
  if (pct === 0) {
    return 'border border-slate-800/50 bg-slate-900/40 text-slate-600 opacity-40';
  }

  switch (act) {
    case 'PUSH':
    case '3BET_PUSH':
    case '4BET_PUSH':
    case 'SQUEEZE_PUSH':
      return 'border border-rose-500 bg-rose-500/30 text-rose-300';
    case 'OPEN_RAISE':
    case 'RAISE':
    case '3BET_RAISE':
    case '4BET_RAISE':
    case 'SQUEEZE':
    case 'BET':
      return 'border border-amber-400 bg-amber-500/20 text-amber-300';
    case 'ISOLATE':
    case 'OPEN_LIMP':
      return 'border border-blue-400 bg-blue-500/25 text-blue-300';
    case 'CALL':
    case 'DEFEND':
      return 'border border-emerald-400 bg-emerald-500/20 text-emerald-300';
    case 'CHECK':
      return 'border border-cyan-400 bg-cyan-500/20 text-cyan-300';
    case 'FOLD':
      return 'border border-stone-700/60 bg-stone-800/60 text-stone-500 opacity-60';
    default:
      return 'border border-slate-700 bg-slate-800 text-slate-200';
  }
};

export default function App() {
  const { session, loading, error, triggerNextHand, resetSession, updateTableSize, updateSession } = usePokerSession();
  const [activeTab, setActiveTab] = useState<ActiveTab>('preflop');
  const [selectedCombo, setSelectedCombo] = useState<string>();
  const [decisionResult, setDecisionResult] = useState<DecisionResult | null>(null);
  const [decisionLoading, setDecisionLoading] = useState(false);
  const [decisionError, setDecisionError] = useState<string>();
  const [facingAction, setFacingAction] = useState<FacingAction>('FIRST_IN');
  const [villainPosition, setVillainPosition] = useState<VillainPosition>('UTG');
  const [flopCards, setFlopCards] = useState<string[]>([]);
  const [postflopResult, setPostflopResult] = useState<DecisionResult | null>(null);
  const [postflopLoading, setPostflopLoading] = useState(false);
  const [postflopError, setPostflopError] = useState<string>();
  const [potType, setPotType] = useState<PotType>('SRP');
  const [heroRole, setHeroRole] = useState<HeroRole>('PFR');
  const [heroPosition, setHeroPosition] = useState<HeroPosition>('IP');
  const preflopRequestId = useRef(0);
  const postflopRequestId = useRef(0);
  const { actionSequence, cycleVillain, clear: clearActionSequence } = useActionSequence();
  const invalidThreeBets = actionSequence.filter((event, index) => event.action === 'THREE_BET'
    && !actionSequence.slice(0, index).some((previous) => previous.action === 'OPEN' || previous.action === 'PUSH'));
  const hasValidVillain = !session || availableVillainPositions(
    session.table_size,
    session.hero_position_label,
  ).length > 0;

  useEffect(() => {
    window.Telegram?.WebApp?.ready();
    window.Telegram?.WebApp?.expand();
  }, []);

  useEffect(() => {
    if (!session) return;
    const positions = availableVillainPositions(session.table_size, session.hero_position_label);
    setVillainPosition(defaultVillainPosition(session.table_size, session.hero_position_label));
    if (!positions.length) setFacingAction('FIRST_IN');
  }, [session?.hero_position_label, session?.table_size]);

  useEffect(() => {
    if (!session) return;

    const requestId = ++preflopRequestId.current;
    setDecisionLoading(true);
    setDecisionError(undefined);

    if (facingAction === 'MULTIWAY' && (!actionSequence.length || invalidThreeBets.length)) {
      setDecisionLoading(false);
      setDecisionResult(null);
      setDecisionError(invalidThreeBets.length ? 'THREE_BET requires an earlier OPEN or PUSH' : undefined);
      return;
    }

    const request = facingAction === 'MULTIWAY'
      ? apiClient.getMultiwayDecision({ hero_combo: selectedCombo, action_sequence: actionSequence })
      : apiClient.getPreflopDecision({
          hero_combo: selectedCombo,
          facing_action: facingAction === 'FIRST_IN' ? undefined : facingAction,
          villain_position: facingAction === 'FIRST_IN' ? undefined : villainPosition,
        });
    request
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
    villainPosition,
    selectedCombo,
    actionSequence,
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
    setFacingAction('FIRST_IN');
    clearActionSequence();
    void triggerNextHand();
  };

  const handleFacingActionChange = (action: FacingAction) => {
    if (facingAction === 'MULTIWAY' && action !== 'MULTIWAY') clearActionSequence();
    setFacingAction(action);
  };

  const handleVillainSeatClick = (position: string) => {
    if (facingAction !== 'MULTIWAY') {
      setFacingAction('MULTIWAY');
    }
    cycleVillain(position as VillainPosition);
  };

  const table = session && (
    <PokerTableMap
      tableSize={session.table_size}
      btnPosition={session.btn_position}
      heroSeat={session.hero_seat}
      heroPositionLabel={session.hero_position_label}
      onSeatClick={activeTab === 'preflop' ? handleVillainSeatClick : undefined}
      seatActions={Object.fromEntries(actionSequence.map((event) => [event.position, event.action]))}
      invalidPositions={invalidThreeBets.map((event) => event.position)}
    />
  );

  return (
    <main className="telegram-shell flex h-[100dvh] max-h-[100dvh] min-w-0 flex-col justify-between overflow-hidden bg-slate-950 p-2 font-sans text-slate-100">
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

      <div className="mx-auto flex min-h-0 w-full max-w-md flex-1 flex-col justify-start gap-1 overflow-x-hidden overflow-y-auto py-1">
        {error && <div className="rounded-lg bg-red-950/60 p-2 text-xs text-red-300">{error}</div>}

        {activeTab === 'preflop' ? (
          <div className="flex w-full min-w-0 shrink-0 flex-col gap-1">
            {table}
            {session && (
              <TableControls
                session={session}
                onNextHand={handleNextHand}
                onResetSession={() => {
                  setSelectedCombo(undefined);
                  void resetSession();
                }}
                onChangeTableSize={(size) => {
                  void updateTableSize(size);
                }}
                onUpdateSession={(payload) => {
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
              action={decisionResult?.action}
              actionRanges={decisionResult?.action_ranges}
            />
            <label className="mx-auto flex w-full max-w-[360px] items-center gap-2 rounded-lg border border-slate-800 bg-slate-900/70 px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">
              Ситуация
              <select
                value={facingAction}
                onChange={(event) => handleFacingActionChange(event.target.value as FacingAction)}
                className="ml-auto min-w-0 max-w-full rounded-md bg-slate-800 px-2 py-1 text-xs normal-case text-slate-200"
              >
                <option value="FIRST_IN">Первое слово / Open</option>
                <option value="OPEN_2.5X">Против Open 2.5x</option>
                <option value="LIMP">Против Limp</option>
                <option value="PUSH">Против Push</option>
                <option value="THREE_BET">Против 3-Bet</option>
                <option value="MULTIWAY" disabled={!hasValidVillain}>Multiway sequence</option>
              </select>
            </label>
            {facingAction !== 'FIRST_IN' && facingAction !== 'MULTIWAY' && (
              <label className="mx-auto flex w-full max-w-[360px] items-center gap-2 rounded-lg border border-slate-800 bg-slate-900/70 px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">
                Соперник
                <select
                  value={villainPosition}
                  onChange={(event) => setVillainPosition(event.target.value as VillainPosition)}
                  className="ml-auto min-w-0 max-w-full rounded-md bg-slate-800 px-2 py-1 text-xs normal-case text-slate-200"
                >
                  {availableVillainPositions(session?.table_size ?? 9, session?.hero_position_label).map((position) => (
                    <option key={position} value={position}>{position}</option>
                  ))}
                </select>
              </label>
            )}
            {facingAction === 'MULTIWAY' && (
              <div className="mx-auto w-full max-w-[380px] rounded-lg border border-slate-700 bg-slate-900/80 p-2 text-center text-[10px] text-slate-300">
                {actionSequence.length ? actionSequence.map((event) => `${event.position}: ${event.action}`).join(' → ') : 'Click opponent seats in action order'}
              </div>
            )}

            {decisionError && <div className="rounded-lg bg-red-950/60 p-2 text-xs text-red-300">{decisionError}</div>}

            <div className="mx-auto flex w-full max-w-[390px] flex-col gap-2 rounded-xl border border-amber-400/30 bg-slate-900 p-3 text-xs shadow-xl">
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

              {!selectedCombo && decisionResult?.range_stats && (
                <div className="flex gap-2 text-[10px] text-slate-400">
                  <span className="rounded bg-slate-800 px-2 py-1">Матрица: <b className="text-white">{decisionResult.range_stats.percentage}%</b></span>
                  <span className="rounded bg-slate-800 px-2 py-1">Комбинаций: <b className="text-white">{decisionResult.range_stats.combos_count}</b></span>
                  <span className="rounded bg-slate-800 px-2 py-1">Ячеек: <b className="text-white">{decisionResult.range_stats.total_matrix_cells}</b></span>
                </div>
              )}

              {decisionResult?.frequencies && Object.keys(decisionResult.frequencies).length > 0 && (
                <div className="space-y-1">
                  <p className="text-[10px] font-black uppercase tracking-wider text-slate-400">
                    Варианты действий и частоты (%):
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(decisionResult.frequencies).filter(([, pct]) => pct > 0).map(([act, pct]) => {
                      const colorClass = getActionColorClass(act, pct);
                      return (
                        <div
                          key={act}
                          className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[10px] font-bold transition-colors ${colorClass}`}
                        >
                          <span>{act.toUpperCase()}</span>
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
                handleNextHand();
              }}
            />
          </div>
        )}
      </div>
    </main>
  );
}