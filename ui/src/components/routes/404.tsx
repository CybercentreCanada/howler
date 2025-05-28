import LinkOffIcon from '@mui/icons-material/LinkOff';
import { Box, Typography } from '@mui/material';
import PageCenter from 'commons/components/pages/PageCenter';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

const NotFoundPage: FC = () => {
  const { t } = useTranslation();
  return (
    <PageCenter width="75%">
      <Box pt={6} textAlign="center" fontSize={200}>
        <LinkOffIcon color="secondary" fontSize="inherit" />
      </Box>
      <Box pb={2}>
        <Typography variant="h2">{t('page.404.title')}</Typography>
      </Box>
      <Box>
        <Typography variant="h5">{t('page.404.description')}</Typography>
      </Box>
    </PageCenter>
  );
};

export default NotFoundPage;
