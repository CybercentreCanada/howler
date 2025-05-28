import { Alert, AlertTitle } from '@mui/material';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';
import { StorageKey } from 'utils/constants';

const DevelopmentBanner: FC = () => {
  const { t } = useTranslation();

  const [disableWarning, setDisableWarning] = useMyLocalStorageItem(StorageKey.DISABLE_FEATURE_WARNING, false);

  if (disableWarning) {
    return null;
  }

  return (
    <Alert severity="warning" variant="outlined" onClose={() => setDisableWarning(true)}>
      <AlertTitle>{t('features.warning.title')}</AlertTitle>
      {t('features.warning.description')}
    </Alert>
  );
};

export default DevelopmentBanner;
