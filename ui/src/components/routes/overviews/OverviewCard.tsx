import { Delete } from '@mui/icons-material';
import { Card, IconButton, Stack, Tooltip, Typography } from '@mui/material';
import FlexOne from 'components/elements/addons/layout/FlexOne';
import HowlerAvatar from 'components/elements/display/HowlerAvatar';
import type { Overview } from 'models/entities/generated/Overview';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

const OverviewCard: FC<{
  overview: Overview;
  className?: string;
  onDelete?: (e: React.MouseEvent<HTMLButtonElement, MouseEvent>, id: string) => void;
}> = ({ overview, className, onDelete }) => {
  const { t } = useTranslation();

  return (
    <Card key={overview.overview_id} variant="outlined" sx={{ p: 1, mb: 1 }} className={className}>
      <Stack direction="row" alignItems="center" spacing={1}>
        <Stack>
          <Typography variant="body1">
            {t(overview.analytic)} - {t(overview.detection ?? 'all')}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            <code>
              <pre>
                {overview.content
                  .split('\n')
                  .filter(line => !!line)
                  .slice(0, 3)
                  .map(content => content.replace(/(.{,64}).+/, '$1'))
                  .join('\n')}
              </pre>
            </code>
          </Typography>
        </Stack>
        <FlexOne />
        <HowlerAvatar sx={{ height: '24px', width: '24px' }} userId={overview.owner} />

        {onDelete && (
          <Tooltip title={t('route.overviews.manager.delete')}>
            <IconButton onClick={e => onDelete(e, overview.overview_id)}>
              <Delete />
            </IconButton>
          </Tooltip>
        )}
      </Stack>
    </Card>
  );
};

export default OverviewCard;
