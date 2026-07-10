import api from 'api';
import type { UserStatus } from 'api/status';
import useMyApi from 'components/hooks/useMyApi';
import { useCallback, useEffect, useRef, useSyncExternalStore } from 'react';

const REFETCH_INTERVAL_MS = 10 * 1000; // 10 seconds

// -- Module-level shared store --

type StoreState = {
  data: UserStatus[] | undefined;
  error: Error | null;
  isLoading: boolean;
};

let state: StoreState = { data: undefined, error: null, isLoading: false };
const listeners = new Set<() => void>();

const subscribe = (listener: () => void): (() => void) => {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
};

const getSnapshot = (): StoreState => state;

const setState = (partial: Partial<StoreState>): void => {
  const next = { ...state, ...partial };

  // Skip update if nothing changed to avoid unnecessary re-renders
  if (next.isLoading === state.isLoading && next.error === state.error && next.data === state.data) {
    return;
  }

  state = next;
  listeners.forEach(listener => listener());
};

// Polling coordination
let pollingIntervalId: ReturnType<typeof setInterval> | null = null;
let pollingCleanup: (() => void) | null = null;
const refetchCallbacks = new Set<() => Promise<void>>();

const invokeRefetch = (): void => {
  // Use any active subscriber's callback — they all fetch the same endpoint
  const callback = refetchCallbacks.values().next().value;
  callback?.();
};

const startPolling = (): void => {
  const shouldPoll = () => !document.hidden && document.hasFocus();

  pollingIntervalId = setInterval(() => {
    if (shouldPoll()) {
      invokeRefetch();
    }
  }, REFETCH_INTERVAL_MS);

  const handleActiveState = () => {
    if (shouldPoll()) {
      invokeRefetch();
    }
  };

  document.addEventListener('visibilitychange', handleActiveState);
  window.addEventListener('focus', handleActiveState);

  pollingCleanup = () => {
    if (pollingIntervalId) {
      clearInterval(pollingIntervalId);
      pollingIntervalId = null;
    }
    document.removeEventListener('visibilitychange', handleActiveState);
    window.removeEventListener('focus', handleActiveState);
    pollingCleanup = null;
  };
};

const stopPolling = (): void => {
  pollingCleanup?.();
  state = { data: undefined, error: null, isLoading: false };
};

// -- Hook --

export const useSharedUserStatusList = () => {
  const { dispatchApi } = useMyApi();

  const refetch = useCallback(async () => {
    // Only set isLoading on the initial fetch (no data yet) to avoid
    // re-renders during background polling that would close open dropdowns.
    if (!state.data) {
      setState({ isLoading: true, error: null });
    }

    try {
      const response = await dispatchApi(api.status.getUserStatuses());
      const prev = state.data;
      const data = JSON.stringify(prev) === JSON.stringify(response) ? prev : response;
      setState({ data, error: null, isLoading: false });
    } catch (_error) {
      const err = _error instanceof Error ? _error : new Error('An unknown error occurred');
      setState({ error: err, isLoading: false });
    }
  }, [dispatchApi]);

  const refetchRef = useRef(refetch);
  refetchRef.current = refetch;

  useEffect(() => {
    const callback = () => refetchRef.current();
    refetchCallbacks.add(callback);

    if (refetchCallbacks.size === 1) {
      refetchRef.current();
      startPolling();
    }

    return () => {
      refetchCallbacks.delete(callback);

      if (refetchCallbacks.size === 0) {
        stopPolling();
      }
    };
  }, []);

  const snapshot = useSyncExternalStore(subscribe, getSnapshot);

  return {
    data: snapshot.data,
    error: snapshot.error,
    isLoading: snapshot.isLoading,
    isError: snapshot.error !== null,
    isSuccess: snapshot.data !== undefined,
    refetch
  };
};
