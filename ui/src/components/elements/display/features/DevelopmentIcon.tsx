import { WarningAmberOutlined } from '@mui/icons-material';
import { Tooltip } from '@mui/material';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';
import { StorageKey } from 'utils/constants';

const DevelopmentIcon: FC = () => {
  const { t } = useTranslation();

  const [disableWarning] = useMyLocalStorageItem(StorageKey.DISABLE_FEATURE_WARNING, false);

  if (!disableWarning) {
    return null;
  }

  return (
    <Tooltip title={t('features.warning.description')}>
      <WarningAmberOutlined color="warning" fontSize="small" />
    </Tooltip>
  );
};

export default DevelopmentIcon;
