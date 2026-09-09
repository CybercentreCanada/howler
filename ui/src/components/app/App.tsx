import { AppAccessibilityProvider } from '@tui/a11y';
import { AppSwitcherProvider, useAppSwitcher } from '@tui/apps';
import {
  AppProvider,
  AppRoot,
  LayoutSkeleton,
  parseTuiClientCookies,
  TUI_THEMES,
  useAppLayout,
  useAppUser
} from '@tui/core';
import { AppDrawerProvider as TuiAppDrawerProvider } from '@tui/drawer';

import type {
  AppBreadcrumbItem,
  AppPreferenceConfigs,
  AppRouterAdapter,
  AppSearchService,
  AppTheme,
  AppUserService
} from '@tui/core';

import { loader } from '@monaco-editor/react';
import {
  Article,
  Book,
  BookRounded,
  Code,
  CreateNewFolder,
  Dashboard,
  Description,
  Edit,
  EditNote,
  FormatListBulleted,
  Help,
  Info,
  Key,
  Person,
  PersonSearch,
  QueryStats,
  SavedSearch,
  Search,
  Settings as SettingsIcon,
  SettingsSuggest,
  Shield,
  Storage,
  Terminal,
  Topic
} from '@mui/icons-material';
import api from 'api';
import Modal from 'components/elements/display/Modal';
import { useMyAccessibility } from 'components/hooks/useMyAccessibility';
import useMyApi from 'components/hooks/useMyApi';
import { APP_COOKIES_DEFAULTS } from 'components/hooks/useMyCookies';
import useMyLocalStorage from 'components/hooks/useMyLocalStorage';
import useMyPreferences from 'components/hooks/useMyPreferences';
import { useMyRouter } from 'components/hooks/useMyRouter';
import useMyTheme from 'components/hooks/useMyTheme';
import useMyUser from 'components/hooks/useMyUser';
import LoginScreen from 'components/logins/Login';
import useLogin from 'components/logins/hooks/useLogin';
import PermissionDeniedPage from 'components/routes/403';
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
import CaseViewer from 'components/routes/cases/CaseViewer';
import Cases from 'components/routes/cases/Cases';
import CaseDashboard from 'components/routes/cases/detail/CaseDashboard';
import CaseObservables from 'components/routes/cases/detail/CaseObservables';
import CaseRules from 'components/routes/cases/detail/CaseRules';
import CaseSearch from 'components/routes/cases/detail/CaseSearch';
import CaseTimeline from 'components/routes/cases/detail/CaseTimeline';
import ItemPage from 'components/routes/cases/detail/ItemPage';
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
import RecordBrowser from 'components/routes/hits/search/RecordBrowser';
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
import 'dayjs/locale/fr-ca';
import duration from 'dayjs/plugin/duration';
import localizedFormat from 'dayjs/plugin/localizedFormat';
import minMax from 'dayjs/plugin/minMax';
import relativeTime from 'dayjs/plugin/relativeTime';
import utc from 'dayjs/plugin/utc';
import i18n from 'i18n';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { Hit } from 'models/entities/generated/Hit';
import * as monaco from 'monaco-editor';
import howlerPluginStore from 'plugins/store';
import { useCallback, useContext, useEffect, useMemo, type FC, type PropsWithChildren, type ReactElement } from 'react';
import { I18nextProvider } from 'react-i18next';
import { PluginProvider, usePluginStore } from 'react-pluggable';
import { createBrowserRouter, Outlet, RouterProvider, useLocation, useNavigate, type UIMatch } from 'react-router';
import { StorageKey } from 'utils/constants';
import useMySearch from '../hooks/useMySearch';
import AppContainer from './AppContainer';
import AnalyticProvider from './providers/AnalyticProvider';
import ApiConfigProvider, { ApiConfigContext } from './providers/ApiConfigProvider';
import AppBarProvider from './providers/AppBarProvider';
import AvatarProvider from './providers/AvatarProvider';
import CustomPluginProvider from './providers/CustomPluginProvider';
import FavouriteProvider from './providers/FavouritesProvider';
import FieldProvider from './providers/FieldProvider';
import GridColumnsProvider from './providers/GridColumnsProvider';
import LocalStorageProvider from './providers/LocalStorageProvider';
import ModalProvider from './providers/ModalProvider';
import OverviewProvider from './providers/OverviewProvider';
import ParameterProvider from './providers/ParameterProvider';
import RecordProvider from './providers/RecordProvider';
import RecordSearchProvider from './providers/RecordSearchProvider';
import SocketProvider from './providers/SocketProvider';
import UserListProvider from './providers/UserListProvider';
import ViewProvider from './providers/ViewProvider';

dayjs.extend(utc);
dayjs.extend(duration);
dayjs.extend(relativeTime);
dayjs.extend(localizedFormat);
dayjs.extend(minMax);
dayjs.locale(i18n.language === 'en' ? 'en' : 'fr-ca');

loader.config({ monaco });

const RoleRoute = ({ roles }) => {
  const appUser = useAppUser<HowlerUser>();

  if (roles.some((role: string) => appUser.user?.roles?.includes(role))) {
    return <Outlet />;
  }

  return <PermissionDeniedPage />;
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

  const onLanguageChange = useCallback((language: 'en' | 'fr') => dayjs.locale(language === 'en' ? 'en' : 'fr-ca'), []);

  useEffect(() => {
    i18n.on('languageChanged', onLanguageChange);
    return () => {
      i18n.off('languageChanged', onLanguageChange);
    };
  }, [onLanguageChange]);

  // Simulate app loading time...
  // e.g. fetching initial app data, etc.
  useEffect(() => {
    void dispatchApi(api.configs.get()).then(data => {
      apiConfig.setConfig(data);

      if (data?.configuration?.ui?.apps) {
        setItems(data.configuration.ui.apps);
      }
    });

    if (appUser.isReady() || (!get(StorageKey.APP_TOKEN) && !get(StorageKey.REFRESH_TOKEN))) {
      return;
    }

    void getUser();
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
        void navigate('/login');
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
  const myUser: AppUserService<HowlerUser> = useMyUser();
  const mySearch: AppSearchService<Hit> = useMySearch();
  const myRouter: AppRouterAdapter = useMyRouter();

  return (
    <ErrorBoundary>
      <AppProvider preferences={myPreferences} user={myUser} search={mySearch} router={myRouter}>
        <CustomPluginProvider>
          <ErrorBoundary>
            <ErrorBoundary>
              <ViewProvider>
                <AvatarProvider>
                  <ModalProvider>
                    <FieldProvider>
                      <LocalStorageProvider>
                        <SocketProvider>
                          <RecordProvider>
                            <OverviewProvider>
                              <AnalyticProvider>
                                <FavouriteProvider>
                                  <UserListProvider>{children}</UserListProvider>
                                </FavouriteProvider>
                              </AnalyticProvider>
                            </OverviewProvider>
                          </RecordProvider>
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
  const myTheme = useMyTheme();
  const myAccessibility = useMyAccessibility();
  const myThemes: AppTheme[] = useMemo(
    () => [
      { id: 'howler', i18nKey: 'route.home.title', configs: myTheme, default: true },
      ...TUI_THEMES.filter(theme => theme.id !== 'howler')
    ],
    [myTheme]
  );
  const tuiCookies = useMemo(() => parseTuiClientCookies(APP_COOKIES_DEFAULTS), []);

  return (
    <I18nextProvider i18n={i18n as any} defaultNS="translation">
      <ApiConfigProvider>
        <PluginProvider pluginStore={howlerPluginStore.pluginStore}>
          <AppBarProvider>
            <AppRoot i18n={i18n} cookies={tuiCookies} themes={myThemes}>
              <TuiAppDrawerProvider>
                <AppAccessibilityProvider preferences={myAccessibility.preferences} features={myAccessibility.features}>
                  <AppSwitcherProvider>
                    <MyAppProvider>
                      <MyApp />
                      <Modal />
                    </MyAppProvider>
                  </AppSwitcherProvider>
                </AppAccessibilityProvider>
              </TuiAppDrawerProvider>
            </AppRoot>
          </AppBarProvider>
        </PluginProvider>
      </ApiConfigProvider>
    </I18nextProvider>
  );
};

// Static breadcrumb entry for a known route.
const crumb = (path: string, i18nKey: string, icon?: ReactElement): AppBreadcrumbItem => ({
  route: path,
  path,
  i18nKey,
  icon
});

// Breadcrumb entry for the currently matched (possibly dynamic) route.
const selfCrumb = (match: UIMatch, i18nKey: string, icon?: ReactElement): AppBreadcrumbItem => ({
  route: match.pathname,
  path: match.pathname,
  i18nKey,
  icon
});

const createRouter = () =>
  createBrowserRouter([
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
          element: <Home />,
          handle: { breadcrumb: (): AppBreadcrumbItem[] => [crumb('/', 'route.home', <Dashboard />)] }
        },
        {
          path: 'hits',
          element: <RecordBrowser />,
          handle: { breadcrumb: (): AppBreadcrumbItem[] => [crumb('/hits', 'route.hits', <Search />)] }
        },
        {
          path: 'search',
          element: <RecordBrowser />,
          handle: { breadcrumb: (): AppBreadcrumbItem[] => [crumb('/search', 'route.search', <Search />)] }
        },
        {
          path: 'hits/:id',
          element: <HitViewer />,
          handle: {
            breadcrumb: (match: UIMatch): AppBreadcrumbItem[] => [
              crumb('/hits', 'route.hits', <Search />),
              selfCrumb(match, 'route.hits.view', <Info />)
            ]
          }
        },

        {
          path: 'cases',
          element: <Cases />,
          handle: { breadcrumb: (): AppBreadcrumbItem[] => [crumb('/cases', 'route.cases', <BookRounded />)] }
        },
        {
          path: 'cases/:id',
          element: (
            <ParameterProvider defaults={{ query: '', indexes: ['hit', 'event', 'case'] }}>
              <CaseViewer />
            </ParameterProvider>
          ),
          handle: {
            breadcrumb: (match: UIMatch): AppBreadcrumbItem[] => [
              crumb('/cases', 'route.cases', <BookRounded />),
              selfCrumb(match, 'route.cases.view')
            ]
          },
          children: [
            {
              index: true,
              element: <CaseDashboard />
            },
            {
              path: 'observables',
              element: <CaseObservables />
            },
            {
              path: 'timeline',
              element: <CaseTimeline />
            },
            {
              path: 'rules',
              element: <CaseRules />
            },
            {
              path: 'search',
              element: <CaseSearch />
            },
            {
              path: '*',
              element: <ItemPage />
            }
          ]
        },
        {
          path: 'templates',
          element: <Templates />,
          handle: {
            breadcrumb: (): AppBreadcrumbItem[] => [crumb('/templates', 'route.templates', <FormatListBulleted />)]
          }
        },
        {
          path: 'templates/view',
          element: <TemplateViewer />,
          handle: {
            breadcrumb: (match: UIMatch): AppBreadcrumbItem[] => [
              crumb('/templates', 'route.templates', <FormatListBulleted />),
              selfCrumb(match, 'route.templates.view', <FormatListBulleted />)
            ]
          }
        },
        {
          path: 'overviews',
          element: <Overviews />,
          handle: { breadcrumb: (): AppBreadcrumbItem[] => [crumb('/overviews', 'route.overviews', <Article />)] }
        },
        {
          path: 'overviews/view',
          element: <OverviewViewer />,
          handle: {
            breadcrumb: (match: UIMatch): AppBreadcrumbItem[] => [
              crumb('/overviews', 'route.overviews', <Article />),
              selfCrumb(match, 'route.overviews.view', <Article />)
            ]
          }
        },
        {
          path: 'dossiers',
          element: <Dossiers />,
          handle: { breadcrumb: (): AppBreadcrumbItem[] => [crumb('/dossiers', 'route.dossiers', <Topic />)] }
        },
        {
          path: 'dossiers/create',
          element: (
            <ParameterProvider>
              <DossierEditor />
            </ParameterProvider>
          ),
          handle: {
            breadcrumb: (match: UIMatch): AppBreadcrumbItem[] => [
              crumb('/dossiers', 'route.dossiers', <Topic />),
              selfCrumb(match, 'route.dossiers.create', <CreateNewFolder />)
            ]
          }
        },
        {
          path: 'dossiers/:id/edit',
          element: (
            <ParameterProvider>
              <DossierEditor />
            </ParameterProvider>
          ),
          handle: {
            breadcrumb: (match: UIMatch): AppBreadcrumbItem[] => [
              crumb('/dossiers', 'route.dossiers', <Topic />),
              selfCrumb(match, 'route.dossiers.edit', <Edit />)
            ]
          }
        },
        {
          path: 'views',
          element: <Views />,
          handle: { breadcrumb: (): AppBreadcrumbItem[] => [crumb('/views', 'route.views', <SavedSearch />)] }
        },
        {
          path: 'views/create',
          element: (
            <ParameterProvider>
              <RecordSearchProvider>
                <GridColumnsProvider viewSource="path">
                  <ViewComposer />
                </GridColumnsProvider>
              </RecordSearchProvider>
            </ParameterProvider>
          ),
          handle: {
            breadcrumb: (): AppBreadcrumbItem[] => [crumb('/views/create', 'route.views.create', <SavedSearch />)]
          }
        },
        {
          path: 'views/:id',
          element: <RecordBrowser />,
          handle: {
            breadcrumb: (match: UIMatch): AppBreadcrumbItem[] => [selfCrumb(match, 'route.views.show', <SavedSearch />)]
          }
        },
        {
          path: 'views/:id/edit',
          element: (
            <ParameterProvider>
              <RecordSearchProvider>
                <GridColumnsProvider viewSource="path">
                  <ViewComposer />
                </GridColumnsProvider>
              </RecordSearchProvider>
            </ParameterProvider>
          ),
          handle: {
            breadcrumb: (match: UIMatch): AppBreadcrumbItem[] => [
              crumb('/views', 'route.views', <SavedSearch />),
              selfCrumb(match, 'route.views.edit', <Edit />)
            ]
          }
        },
        {
          path: 'admin/users',
          element: <UserSearchProvider />,
          handle: {
            breadcrumb: (): AppBreadcrumbItem[] => [crumb('/admin/users', 'route.admin.user.search', <PersonSearch />)]
          }
        },
        {
          path: 'admin/users/:id',
          element: <UserEditor />,
          handle: {
            breadcrumb: (match: UIMatch): AppBreadcrumbItem[] => [
              crumb('/admin/users', 'route.admin.user.search', <PersonSearch />),
              selfCrumb(match, 'route.admin.user.details', <Person />)
            ]
          }
        },
        {
          path: 'analytics',
          element: <AnalyticSearch />,
          handle: { breadcrumb: (): AppBreadcrumbItem[] => [crumb('/analytics', 'route.analytics', <QueryStats />)] }
        },
        {
          path: 'analytics/:id',
          element: <AnalyticDetails />,
          handle: {
            breadcrumb: (match: UIMatch): AppBreadcrumbItem[] => [
              crumb('/analytics', 'route.analytics', <QueryStats />),
              selfCrumb(match, 'route.analytics.view', <Info />)
            ]
          }
        },
        {
          path: 'help',
          element: <HelpDashboard />,
          handle: { breadcrumb: (): AppBreadcrumbItem[] => [crumb('/help', 'route.help', <Help />)] }
        },
        {
          path: 'help/search',
          element: <SearchDocumentation />,
          handle: {
            breadcrumb: (match: UIMatch): AppBreadcrumbItem[] => [
              crumb('/help', 'route.help', <Help />),
              selfCrumb(match, 'route.help.search', <Search />)
            ]
          }
        },
        {
          path: 'help/api',
          element: <ApiDocumentation />,
          handle: {
            breadcrumb: (match: UIMatch): AppBreadcrumbItem[] => [
              crumb('/help', 'route.help', <Help />),
              selfCrumb(match, 'route.help.api', <Storage />)
            ]
          }
        },
        {
          path: 'help/auth',
          element: <AuthDocumentation />,
          handle: {
            breadcrumb: (match: UIMatch): AppBreadcrumbItem[] => [
              crumb('/help', 'route.help', <Help />),
              selfCrumb(match, 'route.help.auth', <Key />)
            ]
          }
        },
        {
          path: 'help/client',
          element: <ClientDocumentation />,
          handle: {
            breadcrumb: (match: UIMatch): AppBreadcrumbItem[] => [
              crumb('/help', 'route.help', <Help />),
              selfCrumb(match, 'route.help.client', <Terminal />)
            ]
          }
        },
        {
          path: 'help/hit',
          element: <HitDocumentation />,
          handle: {
            breadcrumb: (match: UIMatch): AppBreadcrumbItem[] => [
              crumb('/help', 'route.help', <Help />),
              selfCrumb(match, 'route.help.hit', <Shield />)
            ]
          }
        },
        {
          path: 'help/retention',
          element: <RetentionDocumentation />,
          handle: {
            breadcrumb: (match: UIMatch): AppBreadcrumbItem[] => [
              crumb('/help', 'route.help', <Help />),
              selfCrumb(match, 'route.help.retention', <Book />)
            ]
          }
        },
        {
          path: 'help/templates',
          element: <TemplateDocumentation />,
          handle: {
            breadcrumb: (match: UIMatch): AppBreadcrumbItem[] => [
              crumb('/help', 'route.help', <Help />),
              selfCrumb(match, 'route.help.templates', <FormatListBulleted />)
            ]
          }
        },
        {
          path: 'help/actions',
          element: <ActionDocumentation />,
          handle: {
            breadcrumb: (match: UIMatch): AppBreadcrumbItem[] => [
              crumb('/help', 'route.help', <Help />),
              selfCrumb(match, 'route.help.actions', <SettingsSuggest />)
            ]
          }
        },
        {
          path: 'help/notebook',
          element: <NotebookDocumentation />,
          handle: {
            breadcrumb: (match: UIMatch): AppBreadcrumbItem[] => [
              crumb('/help', 'route.help', <Help />),
              selfCrumb(match, 'route.help.notebook', <Description />)
            ]
          }
        },
        {
          path: 'help/overviews',
          element: <OverviewDocumentation />,
          handle: {
            breadcrumb: (match: UIMatch): AppBreadcrumbItem[] => [
              crumb('/help', 'route.help', <Help />),
              selfCrumb(match, 'route.help.overviews', <Article />)
            ]
          }
        },
        {
          path: 'help/views',
          element: <ViewDocumentation />,
          handle: {
            breadcrumb: (match: UIMatch): AppBreadcrumbItem[] => [
              crumb('/help', 'route.help', <Help />),
              selfCrumb(match, 'route.help.views', <SavedSearch />)
            ]
          }
        },
        {
          path: 'settings',
          element: <Settings />,
          handle: {
            breadcrumb: (): AppBreadcrumbItem[] => [crumb('/settings', 'page.settings.sitemap', <SettingsIcon />)]
          }
        },
        {
          path: 'advanced',
          element: <QueryBuilder />,
          handle: { breadcrumb: (): AppBreadcrumbItem[] => [crumb('/advanced', 'route.advanced', <Code />)] }
        },
        {
          path: 'action',
          element: (
            <RoleRoute
              roles={[
                'admin',
                'automation_basic',
                'automation_advanced',
                'actionrunner_basic',
                'actionrunner_advanced'
              ]}
            />
          ),
          children: [
            {
              index: true,
              element: <ActionSearchProvider />,
              handle: { breadcrumb: (): AppBreadcrumbItem[] => [crumb('/action', 'route.actions', <Terminal />)] }
            },
            {
              path: 'integrations',
              element: <Integrations />,
              handle: {
                breadcrumb: (match: UIMatch): AppBreadcrumbItem[] => [
                  crumb('/action', 'route.actions', <Terminal />),
                  selfCrumb(match, 'route.integrations')
                ]
              }
            },
            {
              path: 'execute',
              element: (
                <ParameterProvider>
                  <ActionEditor />
                </ParameterProvider>
              ),
              handle: {
                breadcrumb: (match: UIMatch): AppBreadcrumbItem[] => [
                  crumb('/action', 'route.actions', <Terminal />),
                  selfCrumb(match, 'route.actions.create', <EditNote />)
                ]
              }
            },
            {
              path: ':id',
              children: [
                {
                  index: true,
                  element: <ActionDetails />,
                  handle: {
                    breadcrumb: (match: UIMatch): AppBreadcrumbItem[] => [
                      crumb('/action', 'route.actions', <Terminal />),
                      selfCrumb(match, 'route.actions.view')
                    ]
                  }
                },
                {
                  path: 'edit',
                  element: (
                    <ParameterProvider>
                      <ActionEditor />
                    </ParameterProvider>
                  ),
                  handle: {
                    breadcrumb: (match: UIMatch): AppBreadcrumbItem[] => [
                      crumb('/action', 'route.actions', <Terminal />),
                      selfCrumb(match, 'route.actions.edit', <Edit />)
                    ]
                  }
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
  const router = useMemo(() => createRouter(), []);
  return <RouterProvider router={router} />;
};

export default App;
