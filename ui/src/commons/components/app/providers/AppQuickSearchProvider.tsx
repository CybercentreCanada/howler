import { AppStorageKeys } from 'commons/components/app/AppConstants';
import { AppQuickSearchContext } from 'commons/components/app/AppContexts';
import { type AppSearchService } from 'commons/components/app/AppSearchService';
import { useAppConfigs } from 'commons/components/app/hooks';
import AppSearchServiceProvider from 'commons/components/app/providers/AppSearchServiceProvider';
import useLocalStorageItem from 'commons/components/utils/hooks/useLocalStorageItem';
import { useMemo, type ReactElement } from 'react';

const { LS_KEY_SHOW_QUICK_SEARCH } = AppStorageKeys;

type AppQuickSearchProviderProps = {
  search?: AppSearchService;
  children: ReactElement | ReactElement[];
};

export default function AppQuickSearchProvider({ search, children }: AppQuickSearchProviderProps) {
  const { preferences } = useAppConfigs();
  const [show, setShow] = useLocalStorageItem(LS_KEY_SHOW_QUICK_SEARCH, preferences.defaultShowQuickSearch);
  const context = useMemo(
    () => ({
      show: preferences.allowQuickSearch && show,
      setShow,
      toggle: () => setShow(!show)
    }),
    [preferences.allowQuickSearch, show, setShow]
  );
  return (
    <AppQuickSearchContext.Provider value={context}>
      <AppSearchServiceProvider service={search}>{children}</AppSearchServiceProvider>
    </AppQuickSearchContext.Provider>
  );
}
