import {
  Api,
  Article,
  Book,
  BookRounded,
  Code,
  Dashboard,
  Description,
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
import { Divider, List, ListItemButton, ListItemText, Stack } from '@mui/material';
import { useCookiesStore, type AppPreferenceConfigs, type LeftNavMenuProps } from '@tui/core';
import { AppBarContext } from 'components/app/providers/AppBarProvider';
import Classification from 'components/elements/display/Classification';
import DocumentationButton from 'components/elements/display/DocumentationButton';
import PivotGroupMenuItem from 'components/elements/hit/PivotGroupMenuItem';
import howlerPluginStore from 'plugins/store';
import { Fragment, useContext, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { applyMainMenuOperations } from 'utils/menuUtils';

// This is your App Name that will be displayed in the left drawer and the top navbar
const APP_NAME = 'howler';

const PersonalizationMenuItems = () => {
  const { t } = useTranslation();
  const resetCookies = useCookiesStore(store => store.reset);

  return (
    <>
      <PivotGroupMenuItem />
      <Divider />
      <List dense>
        <ListItemButton dense id="personalization-reset" onClick={resetCookies}>
          <ListItemText>{t('personalization.reset_text')}</ListItemText>
        </ListItemButton>
      </List>
    </>
  );
};

const useMyPreferences = (): AppPreferenceConfigs => {
  const { leftItems, rightItems } = useContext(AppBarContext);

  // The following menu items will show up in the Left Navigation Drawer
  const MENU_ITEMS = useMemo<LeftNavMenuProps[]>(
    () => {
      const defaultMenu: LeftNavMenuProps = {
        id: 'root',
        type: 'menu',
        items: [
          {
            id: 'dashboard',
            type: 'route',
            i18nKey: 'route.home',
            route: '/',
            icon: <Dashboard />
          },
          {
            id: 'cases',
            type: 'route',
            i18nKey: 'route.cases',
            route: '/cases',
            icon: <BookRounded />
          },
          { id: 'divider.1', type: 'slot', component: Divider },
          {
            id: 'search.hit',
            type: 'route',
            i18nKey: 'route.search',
            route: '/search',
            icon: <Search />
          },
          {
            id: 'advanced',
            type: 'route',
            i18nKey: 'route.advanced',
            route: '/advanced',
            icon: <Code />
          },
          { id: 'divider.2', type: 'slot', component: Divider },
          {
            id: 'manage.views',
            type: 'route',
            i18nKey: 'route.views',
            icon: <ManageSearch />,
            route: '/views'
          },
          {
            id: 'manage.analytics',
            type: 'route',
            i18nKey: 'route.analytics',
            icon: <QueryStats />,
            route: '/analytics'
          },
          {
            id: 'manage.templates',
            type: 'route',
            i18nKey: 'route.templates',
            icon: <FormatListBulleted />,
            route: '/templates'
          },
          {
            id: 'manage.overviews',
            type: 'route',
            i18nKey: 'route.overviews',
            icon: <Article />,
            route: '/overviews'
          },
          {
            id: 'manage.dossiers',
            type: 'route',
            i18nKey: 'route.dossiers',
            icon: <Topic />,
            route: '/dossiers'
          },
          {
            id: 'manage.actions',
            type: 'route',
            i18nKey: 'route.actions',
            icon: <Terminal />,
            route: '/action',
            validators: [
              { prop: 'roles', value: 'automation_basic' },
              { prop: 'roles', value: 'automation_advanced' },
              { prop: 'roles', value: 'actionrunner_basic' },
              { prop: 'roles', value: 'actionrunner_advanced' }
            ]
          },
          {
            id: 'action.integrations',
            type: 'route',
            i18nKey: 'route.integrations',
            icon: <Api />,
            route: '/action/integrations',
            validators: [{ prop: 'roles', value: 'automation_basic' }]
          },
          {
            id: 'help',
            type: 'menu',
            i18nKey: 'page.help',
            icon: <Help />,
            items: [
              {
                id: 'help.main',
                type: 'route',
                i18nKey: 'route.help.main',
                route: '/help',
                icon: <HelpCenter />
              },
              {
                id: 'help.client',
                type: 'route',
                i18nKey: 'route.help.client',
                route: '/help/client',
                icon: <Terminal />
              },
              { id: 'help.hit', type: 'route', i18nKey: 'route.help.hit', route: '/help/hit', icon: <Shield /> },
              {
                id: 'help.search',
                type: 'route',
                i18nKey: 'route.help.search',
                route: '/help/search',
                icon: <Search />
              },
              {
                id: 'help.views',
                type: 'route',
                i18nKey: 'route.help.views',
                route: '/help/views',
                icon: <SavedSearch />
              },
              {
                id: 'help.templates',
                type: 'route',
                i18nKey: 'route.help.templates',
                route: '/help/templates',
                icon: <FormatListBulleted />
              },
              {
                id: 'help.overview',
                type: 'route',
                i18nKey: 'route.help.overviews',
                route: '/help/overviews',
                icon: <Article />
              },
              { id: 'help.auth', type: 'route', i18nKey: 'route.help.auth', route: '/help/auth', icon: <Key /> },
              {
                id: 'help.actions',
                type: 'route',
                i18nKey: 'route.help.actions',
                route: '/help/actions',
                icon: <SettingsSuggest />
              },
              {
                id: 'help.notebook',
                type: 'route',
                i18nKey: 'route.help.notebook',
                route: '/help/notebook',
                icon: <Description />
              },
              { id: 'help.api', type: 'route', i18nKey: 'route.help.api', route: '/help/api', icon: <Storage /> },
              {
                id: 'help.retention',
                type: 'route',
                i18nKey: 'route.help.retention',
                route: '/help/retention',
                icon: <Book />
              }
            ]
          }
        ]
      };

      return [applyMainMenuOperations(defaultMenu, howlerPluginStore.mainMenuOperations)];
    },
    // prettier-ignore
    []
  );

  // This is the basic user menu, it is a menu that shows up in account avatar popover.
  const USER_MENU_ITEMS = useMemo(() => {
    // Load plugin menu items first as Settings/Logout generally
    // appear at the end of user menus.
    return [
      ...howlerPluginStore.userMenuItems,
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
    ];
  }, []);

  // This is the basic administrator menu, it is a menu that shows up under the user menu in the account avatar popover.
  const ADMIN_MENU_ITEMS = useMemo(() => {
    return [
      {
        i18nKey: 'adminmenu.users',
        route: '/admin/users',
        icon: <SupervisorAccount />
      },
      ...howlerPluginStore.adminMenuItems
    ];
  }, []);

  // Return memoized config to prevent unnecessary re-renders.
  return useMemo(
    () => ({
      brand: {
        application: APP_NAME,
        appName: 'Howler',
        logo: {
          dark: '/branding/howler/noswoosh-dark.svg',
          light: '/branding/howler/noswoosh-light.svg'
        },
        name: {
          dark: '/branding/howler/name-dark.svg',
          light: '/branding/howler/name-light.svg'
        }
      },
      appLink: '/',
      allowReset: false,
      allowThemeSelection: true,
      topnav: {
        quickSearchParam: 'query',
        quickSearchURI: '/hits',
        profile: {
          menus: {
            user: { i18nKey: 'usermenu', slot: USER_MENU_ITEMS },
            admin: { i18nKey: 'adminmenu', slot: ADMIN_MENU_ITEMS }
          },
          slots: {
            bottom: [<PersonalizationMenuItems key="personalization-menu-items" />]
          }
        },
        slots: {
          breadcrumbs: {
            right: [
              <Stack key="breadcrumbs-right" direction="row" spacing={1} alignItems="center">
                <DocumentationButton />
                {leftItems.map(item => (
                  <Fragment key={item.id}>{item.component}</Fragment>
                ))}
              </Stack>
            ]
          },
          search: {
            left: [
              <Stack key="search-left" direction="row" spacing={1} alignItems="center" pr={1}>
                {rightItems.map(item => (
                  <Fragment key={item.id}>{item.component}</Fragment>
                ))}
                <Classification />
              </Stack>
            ]
          }
        }
      },
      leftnav: {
        menus: MENU_ITEMS,
        width: 280
      }
    }),
    [USER_MENU_ITEMS, ADMIN_MENU_ITEMS, MENU_ITEMS, leftItems, rightItems]
  );
};

export default useMyPreferences;
