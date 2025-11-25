import { loader } from '@monaco-editor/react';
import api from 'api';
import type { AppPreferenceConfigs, AppSiteMapConfigs, AppThemeConfigs } from 'commons/components/app/AppConfigs';
import AppProvider from 'commons/components/app/AppProvider';
import type { AppSearchService } from 'commons/components/app/AppSearchService';
import LayoutSkeleton from 'commons/components/app/AppSkeleton';
import type { AppUserService } from 'commons/components/app/AppUserService';
import { useAppLayout, useAppSwitcher, useAppUser } from 'commons/components/app/hooks';
import Modal from 'components/elements/display/Modal';
import useMyApi from 'components/hooks/useMyApi';
import useMyLocalStorage from 'components/hooks/useMyLocalStorage';
import useMyPreferences from 'components/hooks/useMyPreferences';
import useMySitemap from 'components/hooks/useMySitemap';
import useMyTheme from 'components/hooks/useMyTheme';
import useMyUser from 'components/hooks/useMyUser';
import LoginScreen from 'components/logins/Login';
import useLogin from 'components/logins/hooks/useLogin';
import NotFoundPage from 'components/routes/404';
import ErrorBoundary from 'components/routes/ErrorBoundary';
import Logout from 'components/routes/Logout';
import ActionEditor from 'components/routes/action/edit/ActionEditor';
import ActionDetails from 'components/routes/action/view/ActionDetails';
import ActionSearchProvider from 'components/routes/action/view/ActionSearch';
import Integrations from 'components/routes/action/view/Integrations';
import UserEditor from 'components/routes/admin/users/UserEditor';
import UserSearchProvider from 'components/routes/admin/users/UserSearch';
import QueryBuilder from 'components/routes/advanced/QueryBuilder';
import AnalyticDetails from 'components/routes/analytics/AnalyticDetails';
import AnalyticSearch from 'components/routes/analytics/AnalyticSearch';
import DossierEditor from 'components/routes/dossiers/DossierEditor';
import Dossiers from 'components/routes/dossiers/Dossiers';
import ActionDocumentation from 'components/routes/help/ActionDocumentation';
import ApiDocumentation from 'components/routes/help/ApiDocumentation';
import AuthDocumentation from 'components/routes/help/AuthDocumentation';
import ClientDocumentation from 'components/routes/help/ClientDocumentation';
import HelpDashboard from 'components/routes/help/Help';
import HitDocumentation from 'components/routes/help/HitDocumentation';
import NotebookDocumentation from 'components/routes/help/NotebookDocumentation';
import OverviewDocumentation from 'components/routes/help/OverviewDocumentation';
import RetentionDocumentation from 'components/routes/help/RetentionDocumentation';
import SearchDocumentation from 'components/routes/help/SearchDocumentation';
import TemplateDocumentation from 'components/routes/help/TemplateDocumentation';
import ViewDocumentation from 'components/routes/help/ViewDocumentation';
import HitBrowser from 'components/routes/hits/search/HitBrowser';
import HitViewer from 'components/routes/hits/view/HitViewer';
import Home from 'components/routes/home';
import OverviewViewer from 'components/routes/overviews/OverviewViewer';
import Overviews from 'components/routes/overviews/Overviews';
import Settings from 'components/routes/settings/Settings';
import TemplateViewer from 'components/routes/templates/TemplateViewer';
import Templates from 'components/routes/templates/Templates';
import ViewComposer from 'components/routes/views/ViewComposer';
import Views from 'components/routes/views/Views';
import dayjs from 'dayjs';
import duration from 'dayjs/plugin/duration';
import relativeTime from 'dayjs/plugin/relativeTime';
import utc from 'dayjs/plugin/utc';
import i18n from 'i18n';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { Hit } from 'models/entities/generated/Hit';
import * as monaco from 'monaco-editor';
import howlerPluginStore from 'plugins/store';
import { useContext, useEffect, type FC, type PropsWithChildren } from 'react';
import { I18nextProvider } from 'react-i18next';
import { PluginProvider, usePluginStore } from 'react-pluggable';
import { createBrowserRouter, Outlet, RouterProvider, useLocation, useNavigate } from 'react-router-dom';
import { StorageKey } from 'utils/constants';
import useMySearch from '../hooks/useMySearch';
import AppContainer from './AppContainer';
import AnalyticProvider from './providers/AnalyticProvider';
import ApiConfigProvider, { ApiConfigContext } from './providers/ApiConfigProvider';
import AvatarProvider from './providers/AvatarProvider';
import CustomPluginProvider from './providers/CustomPluginProvider';
import FavouriteProvider from './providers/FavouritesProvider';
import FieldProvider from './providers/FieldProvider';
import HitProvider from './providers/HitProvider';
import LocalStorageProvider from './providers/LocalStorageProvider';
import ModalProvider from './providers/ModalProvider';
import OverviewProvider from './providers/OverviewProvider';
import ParameterProvider from './providers/ParameterProvider';
import SocketProvider from './providers/SocketProvider';
import UserListProvider from './providers/UserListProvider';
import ViewProvider from './providers/ViewProvider';

dayjs.extend(utc);
dayjs.extend(duration);
dayjs.extend(relativeTime);

loader.config({ monaco });

const RoleRoute = ({ role }) => {
  const appUser = useAppUser<HowlerUser>();

  if (appUser.user?.roles?.includes(role)) {
    return <Outlet />;
  }

  return <NotFoundPage />;
};

// Your application's initialization flow.
const MyApp: FC = () => {
  // From this point on, we use the commons' hook.
  const { getUser } = useLogin();
  const { dispatchApi } = useMyApi();
  const appLayout = useAppLayout();
  const appUser = useAppUser<HowlerUser>();
  const location = useLocation();
  const navigate = useNavigate();
  const apiConfig = useContext(ApiConfigContext);
  const { setItems } = useAppSwitcher();
  const { get, set, remove } = useMyLocalStorage();
  const pluginStore = usePluginStore();

  // Simulate app loading time...
  // e.g. fetching initial app data, etc.
  useEffect(() => {
    dispatchApi(api.configs.get()).then(data => {
      apiConfig.setConfig(data);

      if (data?.configuration?.ui?.apps) {
        setItems(data.configuration.ui.apps);
      }
    });

    if (appUser.isReady() || (!get(StorageKey.APP_TOKEN) && !get(StorageKey.REFRESH_TOKEN))) {
      return;
    }

    getUser();
    // eslint-disable-next-line
  }, []);

  useEffect(() => {
    if (appUser.isReady()) {
      appLayout.setReady(true);

      // TODO: Remove in a little while
      remove(StorageKey.ETAG);
    } else if (!get(StorageKey.APP_TOKEN) && !get(StorageKey.REFRESH_TOKEN)) {
      if (location.pathname !== '/login') {
        set(StorageKey.NEXT_LOCATION, location.pathname);
        set(StorageKey.NEXT_SEARCH, location.search);
        navigate('/login');
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appUser.isReady()]);

  for (const plugin of howlerPluginStore.plugins) {
    pluginStore.executeFunction(`${plugin}.setup`)?.();
  }

  // we don't display the skeleton for certain paths
  return (appLayout.ready && apiConfig.config?.indexes) ||
    location.pathname === '/login' ||
    location.pathname === '/logout' ? (
    <AppContainer />
  ) : (
    <LayoutSkeleton />
  );
};

const MyAppProvider: FC<PropsWithChildren> = ({ children }) => {
  const myPreferences: AppPreferenceConfigs = useMyPreferences();
  const myTheme: AppThemeConfigs = useMyTheme();
  const mySitemap: AppSiteMapConfigs = useMySitemap();
  const myUser: AppUserService<HowlerUser> = useMyUser();
  const mySearch: AppSearchService<Hit> = useMySearch();

  return (
    <ErrorBoundary>
      <AppProvider preferences={myPreferences} theme={myTheme} sitemap={mySitemap} user={myUser} search={mySearch}>
        <CustomPluginProvider>
          <ErrorBoundary>
            <ErrorBoundary>
              <ViewProvider>
                <AvatarProvider>
                  <ModalProvider>
                    <FieldProvider>
                      <LocalStorageProvider>
                        <SocketProvider>
                          <HitProvider>
                            <OverviewProvider>
                              <AnalyticProvider>
                                <FavouriteProvider>
                                  <UserListProvider>{children}</UserListProvider>
                                </FavouriteProvider>
                              </AnalyticProvider>
                            </OverviewProvider>
                          </HitProvider>
                        </SocketProvider>
                      </LocalStorageProvider>
                    </FieldProvider>
                  </ModalProvider>
                </AvatarProvider>
              </ViewProvider>
            </ErrorBoundary>
          </ErrorBoundary>
        </CustomPluginProvider>
      </AppProvider>
    </ErrorBoundary>
  );
};

const AppProviderWrapper = () => {
  return (
    <I18nextProvider i18n={i18n as any} defaultNS="translation">
      <ApiConfigProvider>
        <PluginProvider pluginStore={howlerPluginStore.pluginStore}>
          <MyAppProvider>
            <MyApp />
            <Modal />
          </MyAppProvider>
        </PluginProvider>
      </ApiConfigProvider>
    </I18nextProvider>
  );
};

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppProviderWrapper />,
    children: [
      {
        path: 'login',
        element: <LoginScreen />
      },
      {
        path: 'logout',
        element: <Logout />
      },
      {
        index: true,
        element: <Home />
      },
      {
        path: 'hits',
        element: <HitBrowser />
      },
      {
        path: 'search',
        element: <HitBrowser />
      },
      {
        path: 'hits/:id',
        element: <HitViewer />
      },
      {
        path: 'bundles/:id',
        element: <HitBrowser />
      },
      {
        path: 'templates',
        element: <Templates />
      },
      {
        path: 'templates/view',
        element: <TemplateViewer />
      },
      {
        path: 'overviews',
        element: <Overviews />
      },
      {
        path: 'overviews/view',
        element: <OverviewViewer />
      },
      {
        path: 'dossiers',
        element: <Dossiers />
      },
      {
        path: 'dossiers/create',
        element: (
          <ParameterProvider>
            <DossierEditor />
          </ParameterProvider>
        )
      },
      {
        path: 'dossiers/:id/edit',
        element: (
          <ParameterProvider>
            <DossierEditor />
          </ParameterProvider>
        )
      },
      {
        path: 'views',
        element: <Views />
      },
      {
        path: 'views/create',
        element: (
          <ParameterProvider>
            <ViewComposer />
          </ParameterProvider>
        )
      },
      {
        path: 'views/:id',
        element: <HitBrowser />
      },
      {
        path: 'views/:id/edit',
        element: (
          <ParameterProvider>
            <ViewComposer />
          </ParameterProvider>
        )
      },
      {
        path: 'admin/users',
        element: <UserSearchProvider />
      },
      {
        path: 'admin/users/:id',
        element: <UserEditor />
      },
      {
        path: 'analytics',
        element: <AnalyticSearch />
      },
      {
        path: 'analytics/:id',
        element: <AnalyticDetails />
      },
      {
        path: 'help',
        element: <HelpDashboard />
      },
      {
        path: 'help/search',
        element: <SearchDocumentation />
      },
      {
        path: 'help/api',
        element: <ApiDocumentation />
      },
      {
        path: 'help/auth',
        element: <AuthDocumentation />
      },
      {
        path: 'help/client',
        element: <ClientDocumentation />
      },
      {
        path: 'help/hit',
        element: <HitDocumentation />
      },
      {
        path: 'help/retention',
        element: <RetentionDocumentation />
      },
      {
        path: 'help/templates',
        element: <TemplateDocumentation />
      },
      {
        path: 'help/actions',
        element: <ActionDocumentation />
      },
      {
        path: 'help/notebook',
        element: <NotebookDocumentation />
      },
      {
        path: 'help/overviews',
        element: <OverviewDocumentation />
      },
      {
        path: 'help/views',
        element: <ViewDocumentation />
      },
      {
        path: 'settings',
        element: <Settings />
      },
      {
        path: 'advanced',
        element: <QueryBuilder />
      },
      {
        path: 'settings',
        element: <Settings />
      },
      {
        path: 'action',
        element: <RoleRoute role="automation_basic" />,
        children: [
          {
            index: true,
            element: <ActionSearchProvider />
          },
          {
            path: 'integrations',
            element: <Integrations />
          },
          {
            path: 'execute',
            element: (
              <ParameterProvider>
                <ActionEditor />
              </ParameterProvider>
            )
          },
          {
            path: ':id',
            children: [
              {
                index: true,
                element: <ActionDetails />
              },
              {
                path: 'edit',
                element: (
                  <ParameterProvider>
                    <ActionEditor />
                  </ParameterProvider>
                )
              }
            ]
          }
        ]
      },
      ...howlerPluginStore.routes,
      {
        path: '*',
        element: <NotFoundPage />
      }
    ]
  }
]);

const App: FC = () => {
  return <RouterProvider router={router} />;
};

export default App;
