import type { OptionsObject, SnackbarMessage } from 'notistack';
import { useSnackbar } from 'notistack';
import { useCallback, useMemo } from 'react';

const useMySnackbar = () => {
  const { enqueueSnackbar, closeSnackbar } = useSnackbar();
  const snackBarOptions: OptionsObject = useMemo(
    () => ({
      preventDuplicate: true,
      anchorOrigin: {
        vertical: 'bottom',
        horizontal: 'right'
      },
      SnackbarProps: {
        onClick: () => {
          closeSnackbar();
        }
      }
    }),
    [closeSnackbar]
  );

  const enqueue = useCallback(
    (variant: 'error' | 'success' | 'warning' | 'info') =>
      (message: SnackbarMessage, timeout = 5000, options: OptionsObject = {}) =>
        enqueueSnackbar(message, {
          variant,
          autoHideDuration: timeout,
          ...snackBarOptions,
          ...options,
          SnackbarProps: {
            ...(options.SnackbarProps ?? {}),
            onClick: options.SnackbarProps?.onClick
              ? e => {
                  options.SnackbarProps?.onClick(e);
                  snackBarOptions.SnackbarProps.onClick(e);
                }
              : snackBarOptions.SnackbarProps.onClick
          }
        }),
    [enqueueSnackbar, snackBarOptions]
  );

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const showErrorMessage = useCallback(enqueue('error'), [enqueue]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const showWarningMessage = useCallback(enqueue('warning'), [enqueue]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const showSuccessMessage = useCallback(enqueue('success'), [enqueue]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const showInfoMessage = useCallback(enqueue('info'), [enqueue]);

  return useMemo(
    () => ({
      showErrorMessage,
      showWarningMessage,
      showSuccessMessage,
      showInfoMessage
    }),
    [showErrorMessage, showInfoMessage, showSuccessMessage, showWarningMessage]
  );
};

export default useMySnackbar;
