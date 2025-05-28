import { NotificationsActiveOutlined, NotificationsNoneOutlined } from '@mui/icons-material';
import { Badge, IconButton, Tooltip } from '@mui/material';
import { memo, type FC } from 'react';
import { useTranslation } from 'react-i18next';

type TopNavButtonProps = {
  newItems?: number;
  drawer?: boolean;
  onDrawerOpen: () => void;
  onDrawerClose: () => void;
};

export const NotificationTopNavButton: FC<TopNavButtonProps> = memo(
  ({ newItems = 0, drawer = false, onDrawerOpen = () => null, onDrawerClose = () => null }) => {
    const { t } = useTranslation();

    return (
      <Tooltip title={t('notification.title')}>
        <IconButton color="inherit" onClick={() => (drawer ? onDrawerClose() : onDrawerOpen())} size="large">
          <Badge badgeContent={newItems} color="info" max={99}>
            {newItems > 0 ? <NotificationsActiveOutlined /> : <NotificationsNoneOutlined />}
          </Badge>
        </IconButton>
      </Tooltip>
    );
  }
);
