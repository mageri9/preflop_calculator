import type {
  DecisionResult,
  PostflopDecisionRequest,
  PreflopDecisionRequest,
  TableSession,
  ActionEvent,
} from '../types/poker';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api';

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set('Accept', 'application/json');
  headers.set(
    'X-Telegram-Init-Data',
    window.Telegram?.WebApp?.initData ?? '',
  );

  if (options.body) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `HTTP error ${response.status}`);
  }

  return response.json() as Promise<T>;
}

const post = <T>(path: string, payload?: unknown) =>
  request<T>(path, {
    method: 'POST',
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });

export const apiClient = {
  getSession: () => request<TableSession>('/session'),
  nextHand: () => post<TableSession>('/session/next-hand'),
  resetSession: () => post<TableSession>('/session/reset'), // <--- ДОБАВЛЕНО
  setTableSize: (size: number) =>
    post<TableSession>('/session/table-size', { table_size: size }),
  updateSession: (payload: Partial<TableSession>) =>
    post<TableSession>('/session/update', payload),
  getPreflopDecision: (payload: PreflopDecisionRequest) =>
    post<DecisionResult>('/decision/preflop', payload),
  getMultiwayDecision: (payload: { hero_combo?: string; action_sequence: ActionEvent[] }) =>
    post<DecisionResult>('/decision/multiway', payload),
  getPostflopDecision: (payload: PostflopDecisionRequest) =>
    post<DecisionResult>('/decision/postflop', payload),
};
