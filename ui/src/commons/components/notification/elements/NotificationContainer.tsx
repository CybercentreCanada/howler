import { FeedbackOutlined } from '@mui/icons-material';
import { Drawer, useMediaQuery, useTheme } from '@mui/material';
import { type ItemComponentProps } from 'commons/components/app/AppNotificationService';
import { type FeedItem } from 'commons/components/notification';
import { NotificationCloseButton } from 'commons/components/notification/elements/NotificationCloseButton';
import { NotificationHeader } from 'commons/components/notification/elements/NotificationHeader';
import { NotificationItems } from 'commons/components/notification/elements/NotificationItems';
import { memo, useCallback, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';

export type NotificationProps = {
  notifications: FeedItem[];
  ItemComponent: FC<ItemComponentProps>;
  drawer?: boolean;
  initialPageSize?: number;
  loadingPageDelta?: number;
  onDrawerOpen?: () => void;
  onDrawerClose?: () => void;
  inDrawer?: boolean;
  status: string;
  maxDrawerWidth: string;
};

export const NotificationContainer: FC<NotificationProps> = memo(props => {
  const {
    notifications = [],
    drawer = true,
    onDrawerOpen = () => null,
    onDrawerClose = () => null,
    initialPageSize = 10,
    loadingPageDelta = 2,
    ItemComponent = null,
    inDrawer = true,
    status = 'loading',
    maxDrawerWidth = '500px'
  } = props;

  const { t } = useTranslation();
  const theme = useTheme();
  const upSM = useMediaQuery(theme.breakpoints.up('sm'));

  const [pageSize, setPageSize] = useState<number>(initialPageSize);

  const handleLoading = useCallback(() => {
    setPageSize(v => v + loadingPageDelta);
  }, [loadingPageDelta]);

  return inDrawer ? (
    <Drawer
      anchor="right"
      open={drawer}
      onClick={() => (drawer ? onDrawerClose() : onDrawerOpen())}
      PaperProps={{ style: { width: upSM ? '80%' : '100%', maxWidth: maxDrawerWidth } }}
    >
      <div
        style={{
          height: '100%',
          width: '100%',
          overflowX: 'hidden',
          pageBreakBefore: 'avoid',
          pageBreakInside: 'avoid',
          padding: theme.spacing(2.5),
          paddingTop: 0
        }}
      >
        <NotificationHeader icon={<FeedbackOutlined />} title={t('notification.title')}>
          <NotificationCloseButton {...props} />
        </NotificationHeader>
        <NotificationItems
          status={status}
          notifications={notifications}
          pageSize={pageSize}
          handleLoading={handleLoading}
          ItemComponent={ItemComponent}
        />
      </div>
    </Drawer>
  ) : (
    <NotificationItems
      notifications={notifications}
      pageSize={pageSize}
      handleLoading={handleLoading}
      ItemComponent={ItemComponent}
      status={status}
    />
  );
});
