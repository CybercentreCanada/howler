import { OpenInNew } from '@mui/icons-material';
import { Chip, IconButton, Stack, Typography, useTheme } from '@mui/material';
import type { Observable } from 'models/entities/generated/Observable';
import type { FC } from 'react';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

type PreviewProps = {
  observable: Observable;
};

const ObservablePreview: FC<PreviewProps> = ({ observable }) => {
  const { t } = useTranslation();
  const theme = useTheme();

  return (
    <Stack
      flex={1}
      spacing={1}
      sx={{ overflow: 'hidden', borderBottom: `thin solid ${theme.palette.divider}`, pb: 1, mb: 0 }}
    >
      <Stack spacing={1}>
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="body1" fontWeight="bold">
            {observable.event.provider}
          </Typography>
          <div style={{ flex: 1 }} />
          <Chip label={observable.event.kind} />
          {observable.event.reference && (
            <IconButton
              size="small"
              component={Link}
              to={observable.event.reference}
              sx={{ opacity: 1 }}
              target="_blank"
            >
              <OpenInNew fontSize="small" />
            </IconButton>
          )}
        </Stack>

        {observable.event.type && (
          <Typography variant="caption">
            {t('event.type')} - {observable.event.type.join(', ')}
          </Typography>
        )}

        {observable.event.module && (
          <Typography variant="caption">
            {t('event.module')} - {observable.event.module}
          </Typography>
        )}
      </Stack>
    </Stack>
  );
};

export default memo(ObservablePreview);
