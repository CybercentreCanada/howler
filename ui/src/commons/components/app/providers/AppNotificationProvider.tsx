import {
  AppNotificationServiceContext,
  type AppNotificationService,
  type AppNotificationServiceContextType,
  type AppNotificationServiceState
} from 'commons/components/app/AppContexts';
import { useMemo, useState, type ReactElement } from 'react';

const DEFAULT_CONTEXT: AppNotificationServiceContextType = {
  provided: false,
  service: {
    feedUrls: [],
    notificationRenderer: null
  },
  state: { urls: [], set: () => null }
};

export default function AppNotificationServiceProvider({
  service,
  children
}: {
  service?: AppNotificationService;
  children: ReactElement | ReactElement[];
}) {
  // Default implementation of the AppNotificationService using configuration preferences.
  const defaultService: AppNotificationService = useMemo(() => {
    return {
      feedUrls: null,
      notificationRenderer: null
    };
  }, []);

  const [state, setState] = useState<AppNotificationServiceState>(DEFAULT_CONTEXT.state);

  // Memoize context value to prevent unnecessary renders.0
  const context = useMemo(
    () => ({
      provided: !!service,
      service: service || defaultService,
      state: {
        ...state,
        set: setState
      }
    }),
    [service, defaultService, state]
  );

  return <AppNotificationServiceContext.Provider value={context}>{children}</AppNotificationServiceContext.Provider>;
}
