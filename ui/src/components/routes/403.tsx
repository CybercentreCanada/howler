import PersonOffIcon from '@mui/icons-material/PersonOff';
import { Box, Typography } from '@mui/material';
import PageCenter from 'commons/components/pages/PageCenter';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

const PermissionDeniedPage: FC = () => {
  const { t } = useTranslation();
  return (
    <PageCenter width="75%">
      <Box pt={6} textAlign="center" fontSize={200}>
        <PersonOffIcon color="secondary" fontSize="inherit" />
      </Box>
      <Box pb={2}>
        <Typography variant="h2">{t('Error 403')}</Typography>
      </Box>
      <Box>
        <Typography variant="h5">{t('Access Forbidden')}</Typography>
      </Box>
    </PageCenter>
  );
};

export default PermissionDeniedPage;
