import { Delete, ReportProblem } from '@mui/icons-material';
import { Button, Card, IconButton, Stack, Tooltip, Typography } from '@mui/material';
import { ModalContext } from 'components/app/providers/ModalProvider';
import FlexOne from 'components/elements/addons/layout/FlexOne';
import HowlerAvatar from 'components/elements/display/HowlerAvatar';
import ConfirmDeleteModal from 'components/elements/display/modals/ConfirmDeleteModal';
import type { Overview } from 'models/entities/generated/Overview';
import { useCallback, useContext, type FC } from 'react';
import { useTranslation } from 'react-i18next';

const OverviewCard: FC<{
  overview: Overview;
  className?: string;
  error?: boolean;
  onRemove?: (id: string) => Promise<void>;
}> = ({ overview, error, className, onRemove }) => {
  const { t } = useTranslation();
  const { showModal, withConfirmDeleteModal } = useContext(ModalContext);

  const onDelete = useCallback(
    (e: React.MouseEvent<HTMLButtonElement, MouseEvent>, id: string) => {
      e.preventDefault();
      e.stopPropagation();

      withConfirmDeleteModal(async () => {
        await onRemove?.(id);
      });
    },
    [onRemove, withConfirmDeleteModal]
  );

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

        {onRemove && (
          <Tooltip title={t('route.overviews.manager.delete')}>
            <IconButton onClick={e => onDelete?.(e, overview.overview_id)}>
              <Delete />
            </IconButton>
          </Tooltip>
        )}
        {error && (
          <Stack direction="row" justifyContent="end">
            <Stack>
              <Tooltip title={t('error.invalid_detection.action')}>
                <Button
                  startIcon={<ReportProblem />}
                  color="warning"
                  onClick={() =>
                    showModal(
                      <ConfirmDeleteModal
                        onConfirm={() => onRemove?.(overview.overview_id)}
                        title={t('route.overviews.manager.error.modal.title')}
                        description={t('route.overviews.manager.error.modal.description')}
                        preferDelete
                      />
                    )
                  }
                >
                  {t('error.invalid_detection.message')}
                </Button>
              </Tooltip>
            </Stack>
          </Stack>
        )}
      </Stack>
    </Card>
  );
};

export default OverviewCard;
