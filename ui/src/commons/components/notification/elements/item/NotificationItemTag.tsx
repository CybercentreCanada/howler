import { Chip } from '@mui/material';
import { memo, type FC } from 'react';

const TAG_COLOR = {
  new: 'info',
  current: 'success',
  dev: 'warning',
  service: 'secondary',
  blog: 'default'
};

export const NotificationItemTag: FC<{ tag: string }> = memo(
  ({ tag = null }) =>
    tag &&
    tag in TAG_COLOR && (
      <Chip label={tag.toLowerCase()} variant="outlined" size="small" color={TAG_COLOR[tag] ?? 'default'} />
    )
);
