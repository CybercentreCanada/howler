import { Circle } from '@mui/icons-material';
import { Link, Stack, Typography, useTheme } from '@mui/material';
import { type FeedItem } from 'commons/components/notification';
import { memo, type FC } from 'react';

export const NotificationItemTitle: FC<FeedItem> = memo(({ title = null, url = null, _isNew = false }) => {
  const theme = useTheme();

  return !title ? null : !url ? (
    <Typography variant="h6" sx={{ color: theme.palette.primary.main }}>
      <Stack direction="row" alignItems="center" gap={1}>
        {title}
        {_isNew && <Circle sx={{ width: '15px' }} />}
      </Stack>
    </Typography>
  ) : (
    <Typography
      component={Link}
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      underline="none"
      sx={{
        color: theme.palette.primary.main,
        transition: 'color 225ms cubic-bezier(0, 0, 0.2, 1) 0ms',
        '&:hover': {
          color: theme.palette.text.secondary
        }
      }}
      variant="h6"
    >
      <Stack direction="row" alignItems="center" gap={1}>
        {title}
        {_isNew && <Circle sx={{ width: '15px' }} />}
      </Stack>
    </Typography>
  );
});
