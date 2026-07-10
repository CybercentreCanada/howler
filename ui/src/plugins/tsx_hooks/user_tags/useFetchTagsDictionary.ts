import api from 'api';
import type { TagsDictionary } from 'api/tags';
import useMyApi from 'components/hooks/useMyApi';
import { useCallback, useEffect, useRef, useState } from 'react';

type Options = {
  /**
   * Callback function that will be called with the fetched data when the fetch is successful.
   * @param data The tags dictionary fetched from the API.
   * @returns void
   */
  onSuccess?: (data: TagsDictionary) => void;
  /**
   * Callback function that will be called with the error when the fetch fails.
   * @param error The error object representing the error that occurred during the fetch.
   * @returns void
   */
  onError?: (error: Error) => void;
  /**
   * If provided, the hook will refetch the data at the specified interval (in milliseconds).
   */
  refetchInterval?: number;
};

export const useFetchTagsDictionary = (options?: Options) => {
  const { dispatchApi } = useMyApi();

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [data, setData] = useState<TagsDictionary | undefined>(undefined);

  const optionsRef = useRef(options);
  optionsRef.current = options;

  const refetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await dispatchApi(api.tags.getTags());
      setData(response);
      optionsRef.current?.onSuccess?.(response);
    } catch (_error) {
      const err = _error instanceof Error ? _error : new Error('An unknown error occurred');
      setError(err);
      optionsRef.current?.onError?.(err);
    } finally {
      setIsLoading(false);
    }
  }, [dispatchApi]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  useEffect(() => {
    if (!options?.refetchInterval) return;

    const shouldPoll = () => !document.hidden && document.hasFocus();

    const intervalId = setInterval(() => {
      if (shouldPoll()) {
        refetch();
      }
    }, options.refetchInterval);

    const handleActiveState = () => {
      if (shouldPoll()) {
        refetch();
      }
    };

    document.addEventListener('visibilitychange', handleActiveState);
    window.addEventListener('focus', handleActiveState);

    return () => {
      clearInterval(intervalId);
      document.removeEventListener('visibilitychange', handleActiveState);
      window.removeEventListener('focus', handleActiveState);
    };
  }, [options?.refetchInterval, refetch]);

  const isError = error !== null;
  const isSuccess = data !== undefined;

  return { data, isLoading, isError, isSuccess, refetch, error };
};
