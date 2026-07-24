import { OpenInNew } from '@mui/icons-material';
import { Chip, IconButton, Stack, Typography, useTheme } from '@mui/material';
import type { Event } from 'models/entities/generated/Event';
import type { FC } from 'react';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

type PreviewProps = {
  event: Event;
};

const EventPreview: FC<PreviewProps> = ({ event }) => {
  const { t } = useTranslation();
  const theme = useTheme();

  return (
    <Stack
      flex={1}
      spacing={1}
      sx={{ overflow: 'hidden', borderBottom: `thin solid ${theme.palette.divider}`, pb: 1, mb: 0 }}
    >
      <Stack>
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="body1" fontWeight="bold">
            {event.event!.provider}
          </Typography>
          <div style={{ flex: 1 }} />
          <Chip label={event.event!.kind} />
          {event.event!.reference && (
            <IconButton
              size="small"
              component={Link}
              to={event.event!.reference}
              sx={{ opacity: 1 }}
              target="_blank"
              rel="noopener noreferrer"
            >
              <OpenInNew fontSize="small" />
            </IconButton>
          )}
        </Stack>

        {event.event!.type && (
          <Typography variant="caption">
            {t('event.type')} - {event.event!.type.join(', ')}
          </Typography>
        )}

        {event.event!.module && (
          <Typography variant="caption">
            {t('event.module')} - {event.event!.module}
          </Typography>
        )}
      </Stack>
    </Stack>
  );
};

export default memo(EventPreview);
