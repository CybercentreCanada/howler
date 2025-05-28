import { CloseOutlined } from '@mui/icons-material';
import { IconButton } from '@mui/material';
import { type NotificationProps } from 'commons/components/notification/elements/NotificationContainer';
import { memo, type FC } from 'react';

export const NotificationCloseButton: FC<NotificationProps> = memo(
  ({ drawer = false, onDrawerOpen = () => null, onDrawerClose = () => null }) => (
    <div>
      <IconButton onClick={() => (drawer ? onDrawerClose() : onDrawerOpen())} size="large">
        <CloseOutlined fontSize="medium" />
      </IconButton>
    </div>
  )
);
