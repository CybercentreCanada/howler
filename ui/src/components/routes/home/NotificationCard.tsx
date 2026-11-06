import { NotificationsNone } from '@mui/icons-material';
import { ListItemIcon, Menu, MenuItem, Typography } from '@mui/material';
import type { FC } from 'react';

interface NotificationCardProps {
  anchorEl: HTMLElement | null;
  analyticName: string;
  onClose: () => void;
}

const NotificationCard: FC<NotificationCardProps> = ({ anchorEl, analyticName, onClose }) => {
  return (
    <Menu id="notifications-menu" anchorEl={anchorEl} open={!!anchorEl} onClose={onClose}>
      <MenuItem sx={{ width: 360, maxWidth: 'calc(100vw - 32px)', whiteSpace: 'normal' }}>
        <ListItemIcon>
          <NotificationsNone />
        </ListItemIcon>
        <Typography variant="body2">A user commented on your analytic: {analyticName}</Typography>
      </MenuItem>
    </Menu>
  );
};

export default NotificationCard;
