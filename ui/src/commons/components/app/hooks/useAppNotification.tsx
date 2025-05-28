import { AppNotificationServiceContext } from 'commons/components/app/AppContexts';
import { useContext } from 'react';

export function useAppNotification() {
  return useContext(AppNotificationServiceContext);
}
