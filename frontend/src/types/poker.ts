export interface TableSession {
  user_id: number;
  table_size: number;
  btn_position: number;
  hero_seat: number;
  stack_chips: number;
  blind_level: number;
  icm_stage: 'NORMAL' | 'BUBBLE' | 'FINAL_TABLE';
  opponent_style: 'REG' | 'TIGHT' | 'LOOSE';
  has_ante: boolean;
  structure_id: string;
  hero_position_label: string;
  stack_bb: number;
}

export interface PreflopDecisionRequest {
  hero_combo?: string;
  facing_action?: 'OPEN_2.5X' | 'LIMP' | 'PUSH' | 'THREE_BET';
  villain_position?: 'UTG' | 'UTG+1' | 'MP' | 'MP+1' | 'HJ' | 'CO' | 'BTN' | 'SB' | 'BB' | 'BTN/SB';
}

export type VillainPosition = 'UTG' | 'UTG+1' | 'MP' | 'MP+1' | 'HJ' | 'CO' | 'BTN' | 'SB' | 'BB' | 'BTN/SB';
export type ActionType = 'LIMP' | 'OPEN' | 'CALL' | 'THREE_BET' | 'PUSH';
export interface ActionEvent { position: VillainPosition; action: ActionType }

export interface PostflopDecisionRequest {
  hero_cards: string | string[];
  flop_cards: string | string[];
  pot_type?: 'SRP' | '3BP';
  hero_role?: 'PFR' | 'PFC' | 'CALLER';
  hero_position?: 'IP' | 'OOP';
}

export interface DecisionResult {
  action:
    | 'PUSH'
    | 'FOLD'
    | 'OPEN_RAISE'
    | 'OPEN_LIMP'
    | '3BET_PUSH'
    | '3BET_RAISE'
    | '4BET_PUSH'
    | '4BET_RAISE'
    | 'SQUEEZE'
    | 'SQUEEZE_PUSH'
    | 'ISOLATE'
    | 'CALL'
    | 'BET'
    | 'CHECK'
    | 'DEFEND';
  is_in_range: boolean;
  range_str?: string;
  range_stats?: {
    combos_count: number;
    percentage: number;
    total_matrix_cells: number;
  };
  equity_pct?: number;
  recommended_sizing?: string;
  frequencies?: Record<string, number>;
  is_fallback: boolean;
  details: Record<string, any>;
  action_ranges?: {
    push?: Record<string, number>;
    raise?: Record<string, number>;
    isolate?: Record<string, number>;
    call?: Record<string, number>;
  };
}