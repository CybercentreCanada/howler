import ErrorIcon from '@mui/icons-material/Error';
import { Box, Typography } from '@mui/material';
import PageCenter from 'commons/components/pages/PageCenter';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

const ErrorOccured: FC = () => {
  const { t } = useTranslation();
  return (
    <PageCenter width="75%">
      <Box pt={6} textAlign="center" fontSize={200}>
        <ErrorIcon fontSize="inherit" style={{ color: '#f44336' }} />
      </Box>
      <Box pb={2}>
        <Typography variant="h2">{t('page.error.title')}</Typography>
      </Box>
      <Box>
        <Typography variant="h5">{t('page.error.description')}</Typography>
      </Box>
    </PageCenter>
  );
};

export default ErrorOccured;
