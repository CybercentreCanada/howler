import api from 'api';
import type { PatchUserStatusBody, UserStatus } from 'api/status';
import useMyApi from 'components/hooks/useMyApi';
import { useCallback, useRef, useState } from 'react';

type Options = {
  /**
   * Callback function that will be called with the updated data when the mutation is successful.
   * @param data The updated user status returned from the API after a successful mutation.
   * @returns void
   */
  onSuccess?: (data: UserStatus) => void;
  /**
   * Callback function that will be called with the error when the mutation fails.
   * @param error The error object representing the error that occurred during the mutation.
   * @returns void
   */
  onError?: (error: Error) => void;
};

export const useMutateUserStatus = (options?: Options) => {
  const { dispatchApi } = useMyApi();

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const optionsRef = useRef(options);
  optionsRef.current = options;

  const mutate = useCallback(
    async (args: { uname: string; body: PatchUserStatusBody }) => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await dispatchApi(api.status.patchUserStatus(args.uname, args.body));
        optionsRef.current?.onSuccess?.(response);
      } catch (_error) {
        const err = _error instanceof Error ? _error : new Error('An unknown error occurred');
        setError(err);
        optionsRef.current?.onError?.(err);
      } finally {
        setIsLoading(false);
      }
    },
    [dispatchApi]
  );

  return { mutate, isLoading, error };
};
