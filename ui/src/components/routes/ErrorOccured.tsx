import { Error } from '@mui/icons-material';
import { Box, Typography } from '@mui/material';
import PageCenter from 'commons/components/pages/PageCenter';
import howlerPluginStore from 'plugins/store';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';
import { usePluginStore } from 'react-pluggable';

const ErrorOccured: FC = () => {
  const { t } = useTranslation();
  const pluginStore = usePluginStore();
  return (
    <PageCenter width="75%">
      <Box pt={6} textAlign="center" fontSize={200}>
        <Error fontSize="inherit" style={{ color: '#f44336' }} />
      </Box>
      <Box pb={2}>
        <Typography variant="h2">{t('page.error.title')}</Typography>
      </Box>
      <Box>
        <Typography variant="h5">{t('page.error.description')}</Typography>
      </Box>
      {howlerPluginStore.plugins.map(plugin => pluginStore.executeFunction(`${plugin}.support`))}
    </PageCenter>
  );
};

export default ErrorOccured;
