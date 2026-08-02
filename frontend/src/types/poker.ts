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
  facing_action?: 'OPEN_2.5X' | 'LIMP' | 'PUSH';
  villain_position?: 'UTG' | 'MP' | 'CO' | 'BTN';
}

export interface PostflopDecisionRequest {
  hero_cards: string | string[];
  flop_cards: string | string[];
  pot_type?: 'SRP' | '3BP';
  hero_role?: 'PFR' | 'PFC';
  hero_position?: 'IP' | 'OOP';
}

export interface DecisionResult {
  action:
    | 'PUSH'
    | 'FOLD'
    | 'OPEN_RAISE'
    | '3BET_PUSH'
    | '3BET_RAISE'
    | 'CALL'
    | 'BET'
    | 'CHECK';
  is_in_range: boolean;
  range_str?: string;
  range_stats?: {
    combos_count: number;
    percentage: number;
    total_matrix_cells: number;
  };
  recommended_sizing?: string;
  frequencies?: {
    check_pct: number;
    bet_pct: number;
    raise_pct: number;
  };
  is_fallback: boolean;
  details: Record<string, any>;
}
