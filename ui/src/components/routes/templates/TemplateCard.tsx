import { Language, Lock, Person } from '@mui/icons-material';
import { Card, Divider, Stack, Tooltip, Typography } from '@mui/material';
import type { Template } from 'models/entities/generated/Template';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

const TemplateCard: FC<{ template: Template; className?: string }> = ({ template, className }) => {
  const { t } = useTranslation();

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
      </Stack>
    </Card>
  );
};

export default TemplateCard;
