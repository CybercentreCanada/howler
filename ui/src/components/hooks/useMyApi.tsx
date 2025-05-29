import type { HowlerResponse } from 'api';
import useMySnackbar from 'components/hooks/useMySnackbar';
import { useCallback, useMemo } from 'react';

type DispatchApiConfig = {
  throwError?: boolean;
  logError?: boolean;
  showError?: boolean;
  onConflict?: () => Promise<void>;
};

const DEFAULT_CONFIG = {
  throwError: true,
  logError: false,
  showError: true,
  onConflict: null
};

const useMyApi = () => {
  const { showErrorMessage } = useMySnackbar();

  const dispatchApi = useCallback(
    // eslint-disable-next-line comma-spacing
    async <R,>(apiCall: Promise<R>, config: DispatchApiConfig = DEFAULT_CONFIG): Promise<R> => {
      const { throwError, logError, showError, onConflict } = { ...DEFAULT_CONFIG, ...config };
      try {
        const response = await apiCall;
        return response;
      } catch (error) {
        if (error instanceof Error) {
          if (onConflict && [409, 412].includes((error.cause as HowlerResponse<any>)?.api_status_code)) {
            onConflict();
            return null;
          }

          if (showError) {
            showErrorMessage(error.message);
          }

          if (logError) {
            // eslint-disable-next-line no-console
            console.error(error);
          }

          if (throwError) {
            throw error;
          }
        }

        return null;
      }
    },
    [showErrorMessage]
  );

  return useMemo(
    () => ({
      dispatchApi
    }),
    [dispatchApi]
  );
};

export default useMyApi;
