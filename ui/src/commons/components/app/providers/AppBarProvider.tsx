import { AppStorageKeys } from 'commons/components/app/AppConstants';
import { AppBarContext, type AppNotificationService } from 'commons/components/app/AppContexts';
import type { AppSearchService } from 'commons/components/app/AppSearchService';
import { useAppConfigs } from 'commons/components/app/hooks';
import AppBreadcrumbsProvider from 'commons/components/app/providers/AppBreadcrumbsProvider';
import AppNotificationServiceProvider from 'commons/components/app/providers/AppNotificationProvider';
import AppQuickSearchProvider from 'commons/components/app/providers/AppQuickSearchProvider';
import AppSwitcherProvider from 'commons/components/app/providers/AppSwitcherProvider';
import useLocalStorageItem from 'commons/components/utils/hooks/useLocalStorageItem';
import { useMemo, useState, type ReactElement } from 'react';

const { LS_KEY_AUTOHIDE_APPBAR } = AppStorageKeys;

type AppTopNavProviderProps = {
  search?: AppSearchService;
  notification?: AppNotificationService;
  children: ReactElement | ReactElement[];
};

export default function AppBarProvider({ search, notification, children }: AppTopNavProviderProps) {
  const configs = useAppConfigs();
  const [show, setShow] = useState<boolean>(true);
  const [autoHide, setAutoHide] = useLocalStorageItem<boolean>(
    LS_KEY_AUTOHIDE_APPBAR,
    configs.preferences.defaultAutoHideAppbar
  );
  const context = useMemo(
    () => ({
      show,
      autoHide: configs.preferences.allowAutoHideTopbar && autoHide,
      setShow,
      setAutoHide,
      toggleAutoHide: () => setAutoHide(!autoHide)
    }),
    [configs.preferences.allowAutoHideTopbar, show, autoHide, setAutoHide]
  );
  return (
    <AppBarContext.Provider value={context}>
      <AppBreadcrumbsProvider>
        <AppSwitcherProvider>
          <AppNotificationServiceProvider service={notification}>
            <AppQuickSearchProvider search={search}>{children}</AppQuickSearchProvider>
          </AppNotificationServiceProvider>
        </AppSwitcherProvider>
      </AppBreadcrumbsProvider>
    </AppBarContext.Provider>
  );
}
