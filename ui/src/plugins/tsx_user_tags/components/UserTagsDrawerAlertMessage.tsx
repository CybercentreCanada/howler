import { Warning as WarningIcon } from '@mui/icons-material';
import { Alert, alpha, useTheme } from '@mui/material';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

export const UserTagsDrawerAlertMessage = () => {
  const { t } = useTranslation();
  const theme = useTheme();

  const [isDismissed, setIsDismissed] = useState(false);

  if (isDismissed) return null;

  return (
    <Alert
      severity="warning"
      variant="outlined"
      icon={<WarningIcon fontSize="small" />}
      onClose={() => setIsDismissed(true)}
      closeText={t('tsxUserTags.drawer.dismiss')}
      sx={{ m: 2, backgroundColor: alpha(theme.palette.warning.main, 0.075) }}
    >
      {t('tsxUserTags.drawer.alertMessage')}
    </Alert>
  );
};
