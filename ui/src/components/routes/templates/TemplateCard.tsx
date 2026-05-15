import { Language, Lock, Person, ReportProblem } from '@mui/icons-material';
import { Box, Button, Card, Divider, Stack, Tooltip, Typography } from '@mui/material';
import { ModalContext } from 'components/app/providers/ModalProvider';
import ConfirmDeleteModal from 'components/elements/display/modals/ConfirmDeleteModal';
import type { Template } from 'models/entities/generated/Template';
import { useContext, type FC } from 'react';
import { useTranslation } from 'react-i18next';

const DeleteTemplateModal: FC<{ onRemove?: () => void }> = ({ onRemove }) => {
  const { t } = useTranslation();

  return (
    <ConfirmDeleteModal
      onConfirm={onRemove}
      title={t('route.templates.manager.error.modal.title')}
      description={t('route.templates.manager.error.modal.description')}
      preferDelete
    />
  );
};

const TemplateCard: FC<{
  template: Template;
  onRemove?: (templateId: string) => void;
  error?: boolean;
  className?: string;
}> = ({ template, onRemove, error, className }) => {
  const { t } = useTranslation();
  const { showModal } = useContext(ModalContext);

  return (
    <Card key={template.template_id} variant="outlined" sx={{ p: 1, mb: 1 }} className={className}>
      <Stack direction="row" spacing={1}>
        <Tooltip title={t(`route.templates.manager.${template.type}`)}>
          {
            {
              readonly: <Lock />,
              global: <Language />,
              personal: <Person />
            }[template.type]
          }
        </Tooltip>
        <Divider orientation="vertical" flexItem />
        <Stack>
          <Typography variant="body1">
            {t(template.analytic)} - {t(template.detection ?? 'all')}
          </Typography>
          {template.keys.map(key => (
            <Typography key={template.template_id + key} variant="caption" sx={{ ml: 1 }}>
              <code>{key}</code>
            </Typography>
          ))}
        </Stack>
        {error && (
          <Box sx={{ width: '100%', display: 'flex', justifyContent: 'end' }}>
            <Box sx={{ height: 'fitContent' }}>
              <Tooltip title={t('route.templates.manager.error.action')}>
                <Button
                  startIcon={<ReportProblem />}
                  color="warning"
                  onClick={() =>
                    showModal(<DeleteTemplateModal onRemove={() => onRemove && onRemove(template.template_id)} />)
                  }
                >
                  {t('route.templates.manager.error.message')}
                </Button>
              </Tooltip>
            </Box>
          </Box>
        )}
      </Stack>
    </Card>
  );
};

export default TemplateCard;
