import { SNACKBAR_EVENT_ID, useBorealis, type SnackbarEvents } from 'borealis-ui';
import { useAppUser } from 'commons/components/app/hooks';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import useMySnackbar from 'components/hooks/useMySnackbar';
import type { HowlerUser } from 'models/entities/HowlerUser';
import { useContext, useEffect } from 'react';

const useSetup = () => {
  const borealis = useBorealis();
  const appUser = useAppUser<HowlerUser>();
  const apiConfig = useContext(ApiConfigContext);

  const { showSuccessMessage, showErrorMessage, showInfoMessage, showWarningMessage } = useMySnackbar();

  useEffect(() => {
    // eslint-disable-next-line no-console
    console.debug('Initializing borealis snackbar event handler');

    const handleMessage = (event: CustomEvent<SnackbarEvents>) => {
      const { detail } = event;
      if (detail.level === 'success') {
        showSuccessMessage(detail.message, detail.timeout, detail.options);
      } else if (detail.level === 'error') {
        showErrorMessage(detail.message, detail.timeout, detail.options);
      } else if (detail.level === 'info') {
        showInfoMessage(detail.message, detail.timeout, detail.options);
      } else if (detail.level === 'warning') {
        showWarningMessage(detail.message, detail.timeout, detail.options);
      }
    };

    window.addEventListener(SNACKBAR_EVENT_ID, handleMessage);

    return () => {
      window.removeEventListener(SNACKBAR_EVENT_ID, handleMessage);
    };
  }, [showErrorMessage, showInfoMessage, showSuccessMessage, showWarningMessage]);

  useEffect(() => {
    if (!appUser.isReady()) {
      return;
    }

    if (apiConfig.config.configuration?.features?.borealis) {
      borealis.setReady(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiConfig.config.configuration?.features?.borealis, appUser.isReady()]);
};

export default useSetup;
