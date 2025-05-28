import ErrorIcon from '@mui/icons-material/Error';
import { Button, Divider, Stack, Typography } from '@mui/material';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

const LoginErrorModal: FC<{ error: Error }> = ({ error }) => {
  const { t } = useTranslation();

  return (
    <Stack direction="row" spacing={3} alignItems="center">
      <img src="/images/doggie.png" alt="" />
      <Stack>
        <Stack direction="row" alignItems="center" spacing={1}>
          <ErrorIcon color="error" />
          <Typography variant="h5">{t('user.error.modal.header')}</Typography>
        </Stack>
        <Divider orientation="horizontal" sx={{ mt: 1, mb: 1 }} />
        <Typography variant="body1">{t('user.error.modal.body')}</Typography>
        <Typography variant="body1" sx={{ mt: 1 }}>
          {t('user.error.modal.details')}
        </Typography>
        <code style={{ fontSize: '0.8rem' }}>{error.toString()}</code>
        <Stack direction="row" justifyContent="end" sx={{ pt: 1 }}>
          <Button onClick={() => window.location.reload()}>{t('user.error.modal.reload')}</Button>
        </Stack>
      </Stack>
    </Stack>
  );
};

export default LoginErrorModal;
