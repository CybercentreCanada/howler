import { ErrorOutline } from '@mui/icons-material';
import { Grid, Typography, useTheme } from '@mui/material';
import { memo, type FC } from 'react';
import { useTranslation } from 'react-i18next';

export const NotificationError: FC = memo(() => {
  const { t } = useTranslation();
  const theme = useTheme();
  return (
    <Grid
      container
      sx={{ padding: 1, minHeight: theme.spacing(20) }}
      alignContent="center"
      justifyContent="center"
      alignItems="center"
      gap={1}
    >
      <ErrorOutline color="error" sx={{ fontSize: 40 }} />
      <Typography color="error" variant="h6">
        {t('details.notification.error')}
      </Typography>
    </Grid>
  );
});
