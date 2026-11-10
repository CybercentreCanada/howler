import { Delete, MarkEmailRead, Notifications, NotificationsNone } from '@mui/icons-material';
import {
  Alert,
  CircularProgress,
  IconButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Stack,
  Tooltip,
  Typography
} from '@mui/material';
import api from 'api';
import type { Notification } from 'api/v2/notification';
import useMyApi from 'components/hooks/useMyApi';
import { useCallback, useEffect, useState, type Dispatch, type FC, type MouseEvent, type SetStateAction } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';
import { twitterShort } from 'utils/utils';

const NOTIFICATION_ROWS = 25;

interface NotificationCardProps {
  anchorEl: HTMLElement | null;
  onClose: () => void;
  onUnreadChange?: Dispatch<SetStateAction<number>>;
}

const NotificationCard: FC<NotificationCardProps> = ({ anchorEl, onClose, onUnreadChange }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const navigate = useNavigate();
  const open = !!anchorEl;

  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [pending, setPending] = useState<Set<string>>(new Set());

  const runAction = useCallback(async (id: string, action: () => Promise<void>) => {
    setPending(current => new Set(current).add(id));

    try {
      await action();
    } catch {
      // dispatchApi surfaces the error to the user
    } finally {
      setPending(current => {
        const next = new Set(current);
        next.delete(id);
        return next;
      });
    }
  }, []);

  const markRead = useCallback(
    (event: MouseEvent, notification: Notification) => {
      event.stopPropagation();

      void runAction(notification.notification_id, async () => {
        await dispatchApi(api.v2.notification.read.post(notification.notification_id));
        setNotifications(current =>
          current.map(entry =>
            entry.notification_id === notification.notification_id ? { ...entry, read: true } : entry
          )
        );
        onUnreadChange?.(current => Math.max(current - 1, 0));
      });
    },
    [dispatchApi, onUnreadChange, runAction]
  );

  const deleteNotification = useCallback(
    (event: MouseEvent, notification: Notification) => {
      event.stopPropagation();

      void runAction(notification.notification_id, async () => {
        await dispatchApi(api.v2.notification.del(notification.notification_id));
        setNotifications(current => current.filter(entry => entry.notification_id !== notification.notification_id));
        if (!notification.read) {
          onUnreadChange?.(current => Math.max(current - 1, 0));
        }
      });
    },
    [dispatchApi, onUnreadChange, runAction]
  );

  const openNotification = useCallback(
    (notification: Notification) => {
      onClose();
      if (notification.url) {
        void navigate(notification.url);
      }
    },
    [navigate, onClose]
  );

  useEffect(() => {
    if (!open) {
      return;
    }

    const controller = new AbortController();

    const loadNotifications = async () => {
      setLoading(true);
      setError(false);

      try {
        const response = await dispatchApi(
          api.v2.notification.get.user.get({ rows: NOTIFICATION_ROWS }, controller.signal),
          { showError: false }
        );

        if (!controller.signal.aborted) {
          setNotifications(response?.items ?? []);
          if (response) {
            onUnreadChange?.(response.unread);
          }
        }
      } catch {
        if (!controller.signal.aborted) {
          setError(true);
          setNotifications([]);
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    };

    void loadNotifications();

    return () => {
      controller.abort();
    };
  }, [dispatchApi, onUnreadChange, open]);

  const itemSx = { width: 360, maxWidth: 'calc(100vw - 32px)', whiteSpace: 'normal' };

  return (
    <Menu id="notifications-menu" anchorEl={anchorEl} open={open} onClose={onClose}>
      {loading ? (
        <Stack sx={itemSx} alignItems="center" py={2}>
          <CircularProgress size={24} />
        </Stack>
      ) : error ? (
        <Alert severity="error" sx={itemSx}>
          {t('route.home.notifications.error')}
        </Alert>
      ) : notifications.length < 1 ? (
        <Typography variant="body2" color="text.secondary" sx={{ ...itemSx, px: 2, py: 1 }}>
          {t('route.home.notifications.empty')}
        </Typography>
      ) : (
        notifications.map(notification => {
          const busy = pending.has(notification.notification_id);

          return (
            <MenuItem
              key={notification.notification_id}
              id={`notification-${notification.notification_id}`}
              onClick={() => openNotification(notification)}
              sx={itemSx}
            >
              <ListItemIcon>
                {notification.read ? <NotificationsNone color="disabled" /> : <Notifications color="primary" />}
              </ListItemIcon>
              <ListItemText
                primary={t('route.home.notifications.analytic_comment', {
                  commenter: notification.sender,
                  name: notification.resource_name
                })}
                secondary={twitterShort(notification.created)}
                slotProps={{
                  primary: {
                    fontWeight: notification.read ? 'normal' : 'bold',
                    color: notification.read ? 'text.secondary' : 'text.primary'
                  }
                }}
              />
              <Stack direction="row" spacing={0.5} ml={1}>
                {!notification.read && (
                  <Tooltip title={t('route.home.notifications.mark_read')}>
                    <span>
                      <IconButton
                        size="small"
                        aria-label={t('route.home.notifications.mark_read')}
                        disabled={busy}
                        onClick={event => markRead(event, notification)}
                      >
                        <MarkEmailRead fontSize="small" />
                      </IconButton>
                    </span>
                  </Tooltip>
                )}
                <Tooltip title={t('route.home.notifications.delete')}>
                  <span>
                    <IconButton
                      size="small"
                      aria-label={t('route.home.notifications.delete')}
                      disabled={busy}
                      onClick={event => deleteNotification(event, notification)}
                    >
                      <Delete fontSize="small" />
                    </IconButton>
                  </span>
                </Tooltip>
              </Stack>
            </MenuItem>
          );
        })
      )}
    </Menu>
  );
};

export default NotificationCard;
