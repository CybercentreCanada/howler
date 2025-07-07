import {
  Api,
  Article,
  Book,
  Code,
  Dashboard,
  Description,
  Edit,
  ExitToApp,
  FormatListBulleted,
  Help,
  HelpCenter,
  Key,
  ManageSearch,
  QueryStats,
  SavedSearch,
  Search,
  Settings,
  SettingsSuggest,
  Shield,
  Storage,
  SupervisorAccount,
  Terminal,
  Topic
} from '@mui/icons-material';
import { AppBrand } from 'branding/AppBrand';
import type { AppLeftNavElement, AppPreferenceConfigs } from 'commons/components/app/AppConfigs';
import Classification from 'components/elements/display/Classification';
import DocumentationButton from 'components/elements/display/DocumentationButton';
import { useMemo } from 'react';

// This is your App Name that will be displayed in the left drawer and the top navbar
const APP_NAME = 'howler';

const useMyPreferences = (): AppPreferenceConfigs => {
  // The following menu items will show up in the Left Navigation Drawer
  const MENU_ITEMS = useMemo<AppLeftNavElement[]>(
    () => [
      {
        type: 'item',
        element: {
          id: 'dashboard',
          i18nKey: 'route.home',
          route: '/',
          icon: <Dashboard />
        }
      },
      {
        type: 'group',
        element: {
          id: 'views',
          i18nKey: 'route.views.saved',
          icon: <SavedSearch />,
          items: []
        }
      },
      {
        type: 'group',
        element: {
          id: 'analytics',
          i18nKey: 'route.analytics.pinned',
          icon: <QueryStats />,
          items: []
        }
      },
      {
        type: 'item',
        element: {
          id: 'search.hit',
          i18nKey: 'route.search',
          route: '/search',
          icon: <Search />
        }
      },
      {
        type: 'item',
        element: {
          id: 'advanced',
          i18nKey: 'route.advanced',
          route: '/advanced',
          icon: <Code />
        }
      },
      {
        type: 'divider',
        element: null
      },
      {
        type: 'group',
        element: {
          id: 'manage',
          i18nKey: 'manage',
          icon: <Edit />,
          items: [
            {
              id: 'manage.views',
              i18nKey: 'route.views',
              icon: <ManageSearch />,
              nested: true,
              route: '/views'
            },
            {
              id: 'manage.analytics',
              i18nKey: 'route.analytics',
              icon: <QueryStats />,
              nested: true,
              route: '/analytics'
            },
            {
              id: 'manage.templates',
              i18nKey: 'route.templates',
              icon: <FormatListBulleted />,
              nested: true,
              route: '/templates'
            },
            {
              id: 'manage.overviews',
              i18nKey: 'route.overviews',
              icon: <Article />,
              nested: true,
              route: '/overviews'
            },
            {
              id: 'manage.dossiers',
              i18nKey: 'route.dossiers',
              icon: <Topic />,
              nested: true,
              route: '/dossiers'
            },
            {
              id: 'manage.actions',
              i18nKey: 'route.actions',
              icon: <Terminal />,
              nested: true,
              route: '/action',
              userPropValidators: [{ prop: 'roles', value: 'automation_basic' }]
            },
            {
              id: 'action.integrations',
              i18nKey: 'route.integrations',
              icon: <Api />,
              nested: true,
              route: '/action/integrations',
              userPropValidators: [{ prop: 'roles', value: 'automation_basic' }]
            }
          ]
        }
      },
      {
        type: 'divider',
        element: null
      },
      {
        type: 'group',
        element: {
          id: 'help',
          i18nKey: 'page.help',
          icon: <Help />,
          items: [
            {
              id: 'help.main',
              i18nKey: 'route.help.main',
              route: '/help',
              nested: true,
              icon: <HelpCenter />
            },
            {
              id: 'help.client',
              i18nKey: 'route.help.client',
              route: '/help/client',
              nested: true,
              icon: <Terminal />
            },
            { id: 'help.hit', i18nKey: 'route.help.hit', route: '/help/hit', nested: true, icon: <Shield /> },
            { id: 'help.search', i18nKey: 'route.help.search', route: '/help/search', nested: true, icon: <Search /> },
            {
              id: 'help.views',
              i18nKey: 'route.help.views',
              route: '/help/views',
              nested: true,
              icon: <SavedSearch />
            },
            {
              id: 'help.templates',
              i18nKey: 'route.help.templates',
              route: '/help/templates',
              nested: true,
              icon: <FormatListBulleted />
            },
            {
              id: 'help.overview',
              i18nKey: 'route.help.overviews',
              route: '/help/overviews',
              nested: true,
              icon: <Article />
            },
            { id: 'help.auth', i18nKey: 'route.help.auth', route: '/help/auth', nested: true, icon: <Key /> },
            {
              id: 'help.actions',
              i18nKey: 'route.help.actions',
              route: '/help/actions',
              nested: true,
              icon: <SettingsSuggest />
            },
            {
              id: 'help.notebook',
              i18nKey: 'route.help.notebook',
              route: '/help/notebook',
              nested: true,
              icon: <Description />
            },
            { id: 'help.api', i18nKey: 'route.help.api', route: '/help/api', nested: true, icon: <Storage /> },
            {
              id: 'help.retention',
              i18nKey: 'route.help.retention',
              route: '/help/retention',
              nested: true,
              icon: <Book />
            }
          ]
        }
      }
    ],
    // prettier-ignore
    []
  );

  // This is the basic user menu, it is a menu that shows up in account avatar popover.
  const USER_MENU_ITEMS = useMemo(
    () => [
      {
        i18nKey: 'usermenu.settings',
        route: '/settings',
        icon: <Settings />
      },
      {
        i18nKey: 'usermenu.logout',
        route: '/logout',
        icon: <ExitToApp />
      }
    ],
    []
  );

  // This is the basic administrator menu, it is a menu that shows up under the user menu in the account avatar popover.
  const ADMIN_MENU_ITEMS = useMemo(
    () => [
      {
        i18nKey: 'adminmenu.users',
        route: '/admin/users',
        icon: <SupervisorAccount />
      }
    ],
    []
  );

  // Return memoized config to prevent unnecessary re-renders.
  return useMemo(
    () => ({
      appName: '',
      allowGravatar: false,
      appIconDark: <AppBrand application={APP_NAME} variant="app" />,
      appIconLight: <AppBrand application={APP_NAME} variant="app" />,
      bannerLight: <AppBrand application={APP_NAME} variant="banner-vertical" size="large" />,
      bannerDark: <AppBrand application={APP_NAME} variant="banner-vertical" size="large" />,
      defaultShowQuickSearch: true,
      avatarD: 'retro',
      topnav: {
        apps: [],
        userMenu: USER_MENU_ITEMS,
        userMenuI18nKey: 'usermenu',
        adminMenu: ADMIN_MENU_ITEMS,
        adminMenuI18nKey: 'adminmenu',
        quickSearchParam: 'query',
        quickSearchURI: '/hits',
        leftAfterBreadcrumbs: <DocumentationButton />,
        rightBeforeSearch: <Classification />
      },
      leftnav: {
        elements: MENU_ITEMS
      }
    }),
    [USER_MENU_ITEMS, ADMIN_MENU_ITEMS, MENU_ITEMS]
  );
};

export default useMyPreferences;
