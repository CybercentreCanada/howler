import { Box, Link, Typography } from '@mui/material';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

const PivotTooltip: FC<{ dossier: Dossier; resolvedUrl: string }> = ({ dossier, resolvedUrl }) => {
  const dossierUrl = `/dossiers/${dossier.dossier_id}/edit?tab=leads&query=${encodeURIComponent(dossier.query)}`;
  const { t } = useTranslation();

  return (
    <Box sx={{ maxWidth: 300 }}>
      <Typography variant="subtitle2">{dossier.title}</Typography>
      <Typography variant="body2" color="text.secondary">
        {dossier.owner}
      </Typography>
      <Box sx={{ mt: 2, wordBreak: 'break-all' }}>
        <Typography variant="caption" display="block">
          {t('pivot.url')}
        </Typography>
        <Link href={resolvedUrl} target="_blank" rel="noopener noreferrer" underline="hover">
          {resolvedUrl}
        </Link>
      </Box>
      <Box sx={{ mt: 2 }}>
        <Link href={dossierUrl} target="_blank" rel="noopener noreferrer" underline="hover">
          {t('pivot.dossier.open')}
        </Link>
      </Box>
    </Box>
  );
};

export default PivotTooltip;
