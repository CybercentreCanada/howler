import { Delete, Language, Person } from '@mui/icons-material';
import { Box, Card, IconButton, Stack, Tooltip, Typography } from '@mui/material';
import FlexOne from 'components/elements/addons/layout/FlexOne';
import HowlerAvatar from 'components/elements/display/HowlerAvatar';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

const DossierCard: FC<{
  dossier: Dossier;
  className?: string;
  onDelete?: (e: React.MouseEvent<HTMLButtonElement, MouseEvent>, id: string) => void;
}> = ({ dossier, className, onDelete }) => {
  const { t } = useTranslation();

  return (
    <Card key={dossier.dossier_id} variant="outlined" sx={{ p: 1, mb: 1 }} className={className}>
      <Stack direction="row" alignItems="center" spacing={1}>
        <Stack>
          <Typography variant="body1" display="flex" alignItems="start">
            <Tooltip title={t(`route.dossiers.manager.${dossier.type}`)}>
              {dossier.type === 'personal' ? <Person fontSize="small" /> : <Language fontSize="small" />}
            </Tooltip>
            <Box component="span" ml={1}>
              {dossier.title}
            </Box>
          </Typography>
          <Typography variant="caption" color="text.secondary">
            <code>{dossier.query}</code>
          </Typography>
        </Stack>
        <FlexOne />

        <HowlerAvatar sx={{ height: '24px', width: '24px' }} userId={dossier.owner} />

        {onDelete && (
          <Tooltip title={t('route.dossiers.manager.delete')}>
            <IconButton onClick={e => onDelete(e, dossier.dossier_id)}>
              <Delete />
            </IconButton>
          </Tooltip>
        )}
      </Stack>
    </Card>
  );
};

export default DossierCard;
