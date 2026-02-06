import { SNACKBAR_EVENT_ID, type SnackbarEvents } from '@cccsaurora/clue-ui/data/event';
import useClue from '@cccsaurora/clue-ui/hooks/useClue';
import { useAppUser } from 'commons/components/app/hooks/useAppUser';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import useMySnackbar from 'components/hooks/useMySnackbar';
import type { HowlerUser } from 'models/entities/HowlerUser';
import { useContext, useEffect } from 'react';

const useSetup = () => {
  const clue = useClue();
  const appUser = useAppUser<HowlerUser>();
  const { config } = useContext(ApiConfigContext);

  const { showSuccessMessage, showErrorMessage, showInfoMessage, showWarningMessage } = useMySnackbar();

  const features: { [index: string]: boolean } = config.configuration?.features ?? {};

  useEffect(() => {
    // eslint-disable-next-line no-console
    console.debug('Initializing clue snackbar event handler');

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

    if (features.borealis || features.clue) {
      clue.setReady(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [features, appUser.isReady()]);
};

export default useSetup;
