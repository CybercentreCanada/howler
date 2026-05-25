import { Delete, Language, ManageSearch, Person } from '@mui/icons-material';
import { Box, Card, Chip, Divider, Grid, IconButton, Stack, Tooltip, Typography } from '@mui/material';
import HowlerAvatar from 'components/elements/display/HowlerAvatar';
import { isEmpty } from 'lodash-es';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

const DossierCard: FC<{
  dossier: Dossier;
  className?: string;
  onDelete?: (e: React.MouseEvent<HTMLButtonElement, MouseEvent>, id: string) => void;
}> = ({ dossier, className, onDelete }) => {
  const { t, i18n } = useTranslation();

  return (
    <Card key={dossier.dossier_id} variant="outlined" sx={{ p: 1, mb: 1 }} className={className}>
      <Stack direction="row" alignItems="center" spacing={1} sx={{ '& > *': { flexShrink: 0 } }}>
        <Stack sx={{ flex: 1 }}>
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
          <Grid container spacing={1} sx={{ mt: 1 }}>
            {dossier.leads?.map((lead, index) => (
              <Grid item key={lead.format + lead.label?.en}>
                <Chip
                  sx={{ maxWidth: '300px' }}
                  clickable
                  label={`${lead.label?.[i18n.language] ?? t('unknown')} (${lead.format})`}
                  size="small"
                  component={Link}
                  to={`/dossiers/${dossier.dossier_id}/edit?tab=leads&lead=${index}`}
                  onClick={e => e.stopPropagation()}
                />
              </Grid>
            ))}
            {!isEmpty(dossier.leads) && !isEmpty(dossier.pivots) && (
              <Grid item>
                <Divider orientation="vertical" />
              </Grid>
            )}
            {dossier.pivots?.map((pivot, index) => (
              <Grid item key={pivot.format + pivot.label?.en}>
                <Chip
                  sx={{ maxWidth: '300px' }}
                  clickable
                  label={`${pivot.label?.[i18n.language] ?? t('unknown')} (${pivot.format})`}
                  size="small"
                  component={Link}
                  to={`/dossiers/${dossier.dossier_id}/edit?tab=pivots&pivot=${index}`}
                  onClick={e => e.stopPropagation()}
                />
              </Grid>
            ))}
          </Grid>
        </Stack>

        <HowlerAvatar sx={{ height: '28px', width: '28px' }} userId={dossier.owner} />
        <Tooltip title={t('route.dossiers.manager.openinsearch')}>
          <IconButton component={Link} to={`/search?query=${dossier.query}`} onClick={e => e.stopPropagation()}>
            <ManageSearch />
          </IconButton>
        </Tooltip>
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
