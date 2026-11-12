import { Edit, NotificationsActiveOutlined, NotificationsNoneOutlined, Settings } from '@mui/icons-material';
import {
  Badge,
  FormControl,
  FormLabel,
  IconButton,
  ListItemIcon,
  Menu,
  MenuItem,
  Slider,
  Tooltip
} from '@mui/material';
import { useState, type Dispatch, type FC, type SetStateAction } from 'react';
import { useTranslation } from 'react-i18next';
import NotificationCard from './NotificationCard';

const REFRESH_RATES = [15, 30, 60, 300];

interface HomeSettingsProps {
  /** Whether the dashboard is currently in edit mode. Disables the "Edit" menu item. */
  isEditing: boolean;
  /** Current auto-refresh interval in seconds. */
  refreshRate: number;
  /** Called when the user selects a new refresh rate. */
  onRefreshRateChange: (rate: number) => void;
  /** Called when the user clicks the "Edit" menu item. */
  onEdit: () => void;
  /** Number of unread notifications for the current user. */
  unreadNotifications: number;
  /** Called when the notification card changes the unread count. */
  onUnreadNotificationsChange: Dispatch<SetStateAction<number>>;
}

const HomeSettings: FC<HomeSettingsProps> = ({
  isEditing,
  refreshRate,
  onRefreshRateChange,
  onEdit,
  unreadNotifications,
  onUnreadNotificationsChange
}) => {
  const { t } = useTranslation();
  const [settingsAnchorEl, setSettingsAnchorEl] = useState<null | HTMLElement>(null);
  const [notificationAnchorEl, setNotificationAnchorEl] = useState<null | HTMLElement>(null);

  return (
    <>
      <Tooltip title={t('page.dashboard.settings.edit')}>
        <IconButton
          aria-label="Open dashboard settings"
          onClick={e => setSettingsAnchorEl(e.currentTarget)}
          size="small"
        >
          <Settings color="primary" />
        </IconButton>
      </Tooltip>
      <Menu
        id="settings-menu"
        anchorEl={settingsAnchorEl}
        open={!!settingsAnchorEl}
        onClose={() => setSettingsAnchorEl(null)}
      >
        <MenuItem
          disabled={isEditing}
          onClick={() => {
            setSettingsAnchorEl(null);
            onEdit();
          }}
        >
          <ListItemIcon>
            <Edit />
          </ListItemIcon>
          {t('page.dashboard.settings.edit')}
        </MenuItem>
        <MenuItem disableRipple disableTouchRipple sx={{ '&:hover': { bgcolor: 'transparent' }, cursor: 'default' }}>
          <FormControl sx={{ px: 2, py: 1, minWidth: 250, pointerEvents: 'auto' }}>
            <FormLabel id="refresh-rate-label" sx={{ mb: 2 }}>
              {t('page.dashboard.settings.refreshRate')}
            </FormLabel>
            <Slider
              aria-labelledby="refresh-rate-label"
              value={REFRESH_RATES.indexOf(refreshRate)}
              onChange={(_, value) => onRefreshRateChange(REFRESH_RATES[value as number])}
              step={1}
              marks={[
                { value: 0, label: '15s' },
                { value: 1, label: '30s' },
                { value: 2, label: '1m' },
                { value: 3, label: '5m' }
              ]}
              min={0}
              max={3}
              valueLabelDisplay="auto"
              valueLabelFormat={value => {
                const rates = ['15s', '30s', '1m', '5m'];
                return rates[value] || '';
              }}
            />
          </FormControl>
        </MenuItem>
      </Menu>
      <Tooltip title={t('route.home.notifications.title')}>
        <IconButton
          aria-label="Open notifications"
          onClick={e => setNotificationAnchorEl(e.currentTarget)}
          size="small"
        >
          <Badge id="notification-badge" badgeContent={unreadNotifications} color="error" max={99}>
            {unreadNotifications > 0 ? (
              <NotificationsActiveOutlined id="notifications-active-icon" color="primary" />
            ) : (
              <NotificationsNoneOutlined id="notifications-none-icon" color="primary" />
            )}
          </Badge>
        </IconButton>
      </Tooltip>
      <NotificationCard
        anchorEl={notificationAnchorEl}
        onClose={() => setNotificationAnchorEl(null)}
        onUnreadChange={onUnreadNotificationsChange}
      />
    </>
  );
};

export default HomeSettings;
