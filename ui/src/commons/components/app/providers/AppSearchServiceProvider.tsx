import {
  AppSearchServiceContext,
  type AppSearchServiceContextType,
  type AppSearchServiceState
} from 'commons/components/app/AppContexts';
import type { AppSearchService } from 'commons/components/app/AppSearchService';
import { useAppConfigs } from 'commons/components/app/hooks';
import { useMemo, useState, type ReactElement } from 'react';
import { useNavigate } from 'react-router';

const DEFAULT_CONTEXT: AppSearchServiceContextType = {
  provided: false,
  service: {
    itemRenderer: () => <div />
  },
  state: {
    searching: false,
    menu: false,
    mode: 'inline',
    items: null,
    set: () => null
  }
};

export default function AppSearchServiceProvider<T = any>({
  service,
  children
}: {
  service?: AppSearchService<T>;
  children: ReactElement | ReactElement[];
}) {
  // Hooks required for default implementation.
  const navigate = useNavigate();
  const { preferences } = useAppConfigs();

  // Default implementation of the AppSearchService using configuration preferences.
  const defaultService: AppSearchService<any> = useMemo(() => {
    const searchUri = preferences.topnav.quickSearchURI;
    const params = preferences.topnav.quickSearchParam;
    return {
      onEnter: (value: string) => {
        navigate(`${searchUri}?${params}=${encodeURIComponent(value)}`);
      },
      itemRenderer: () => <div />
    };
  }, [preferences, navigate]);

  // The state of the search service.
  const [state, setState] = useState<AppSearchServiceState<T>>(DEFAULT_CONTEXT.state);

  // Memoize context value to prevent unnecessary renders.
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

  return <AppSearchServiceContext.Provider value={context}>{children}</AppSearchServiceContext.Provider>;
}
