import api from 'api';
import type { UserTags } from 'api/tags';
import { useAppUser } from 'commons/components/app/hooks';
import useMyApi from 'components/hooks/useMyApi';
import { useCallback, useRef, useState } from 'react';

type Options = {
  /**
   * Callback function that will be called with the updated data when the mutation is successful.
   * @param success A boolean indicating whether the mutation was successful.
   * @returns void
   */
  onSuccess?: (data: boolean, variables: { tags: UserTags }) => void;
  /**
   * Callback function that will be called with the error when the mutation fails.
   * @param error The error object representing the error that occurred during the mutation.
   * @returns void
   */
  onError?: (error: Error) => void;
};

export const useMutateUserTags = (options?: Options) => {
  const { dispatchApi } = useMyApi();
  const { user } = useAppUser();

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const optionsRef = useRef(options);
  optionsRef.current = options;

  const mutate = useCallback(
    async (tags: UserTags) => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await dispatchApi(api.user.put(user.username, { tags }));
        optionsRef.current?.onSuccess?.(response, { tags });
      } catch (_error) {
        const err = _error instanceof Error ? _error : new Error('An unknown error occurred');
        setError(err);
        optionsRef.current?.onError?.(err);
      } finally {
        setIsLoading(false);
      }
    },
    [dispatchApi, user.username]
  );

  return { mutate, isLoading, error };
};
