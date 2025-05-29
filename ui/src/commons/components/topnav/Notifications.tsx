import { useAppNotification } from 'commons/components/app/hooks/useAppNotification';
import { Notification } from 'commons/components/notification';
import { type FC } from 'react';

export const Notifications: FC = () => {
  const { service, state } = useAppNotification();

  return (
    <Notification
      urls={service.feedUrls || state.urls}
      notificationItem={service.notificationRenderer}
      maxDrawerWidth="800px"
      openIfNew
    />
  );
};
