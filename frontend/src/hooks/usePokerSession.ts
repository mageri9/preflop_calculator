import { useCallback, useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import type { TableSession } from '../types/poker';

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Неизвестная ошибка';
}

export function usePokerSession() {
  const [session, setSession] = useState<TableSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const runSessionAction = useCallback(
    async (action: () => Promise<TableSession>) => {
      setLoading(true);
      setError(null);

      try {
        const nextSession = await action();
        setSession(nextSession);
        return nextSession;
      } catch (caughtError) {
        setError(getErrorMessage(caughtError));
        return null;
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    void runSessionAction(apiClient.getSession);
  }, [runSessionAction]);

  const triggerNextHand = useCallback(
    () => runSessionAction(apiClient.nextHand),
    [runSessionAction],
  );

  const updateTableSize = useCallback(
    (size: number) => runSessionAction(() => apiClient.setTableSize(size)),
    [runSessionAction],
  );

  const updateSession = useCallback(
    (payload: Partial<TableSession>) =>
      runSessionAction(() => apiClient.updateSession(payload)),
    [runSessionAction],
  );

  return {
    session,
    loading,
    error,
    triggerNextHand,
    updateTableSize,
    updateSession,
  };
}
