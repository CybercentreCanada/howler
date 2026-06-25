import { Box, Typography } from '@mui/material';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

const NotebookTooltip: FC = () => {
  const { t } = useTranslation();

  return (
    <Box sx={{ maxWidth: 300 }}>
      <Typography variant="subtitle2">{t('notebook.title')}</Typography>
      <Typography variant="body2" color="text.secondary">
        {t('notebook.opens.panel')}
      </Typography>
    </Box>
  );
};

export default NotebookTooltip;
