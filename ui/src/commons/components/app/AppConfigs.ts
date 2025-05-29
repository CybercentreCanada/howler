import type { Components, PaletteMode, PaletteOptions, Theme } from '@mui/material';
import type { AppUserValidatedProp } from 'commons/components/app/AppUserService';
import type { GravatarD } from 'commons/components/display/AppAvatar';
import type { ReactElement, ReactNode } from 'react';
import type { To } from 'react-router-dom';

// Specification interface for the 'useAppConfigs' hook.
export type AppConfigs = {
  preferences?: AppPreferenceConfigs; // The app's preferences config.
  theme?: AppThemeConfigs; // The app's theme config.
  sitemap?: AppSiteMapConfigs; // The apps's sitemap configs.
};

// Specification interface for the AppProvider's 'preferences' attribute.
export type AppPreferenceConfigs = {
  appName: string; // Name of your app, it will show up in the drawer and the top nav bar
  appLink?: To; // Route to navigate to when the icon on the left nav bar is pressed
  appIconDark: ReactElement<any>; // Small dark mode logo of your app used in drawer and top nav bar
  appIconLight: ReactElement<any>; // Small light mode logo of your app used in drawer and top nav bar
  bannerDark?: ReactElement<any>; // Your dark mode app banner, will be use in the loading screen, login and logout pages
  bannerLight?: ReactElement<any>; // Your dark mode app banner, will be use in the loading screen, login and logout pages
  allowAutoHideTopbar?: boolean; // Allow the user to toggle on/off the topbar autohide feature
  allowBreadcrumbs?: boolean; // Allow the user to toggle on/off the breadcrumb
  allowGravatar?: boolean; // Will use gravatar to populate the UserProfile avatar picture (using the user's email).
  allowQuickSearch?: boolean; // Allow the user toggle on/off the quick search
  allowReset?: boolean; // Allow the user to reset preferences to the default values
  allowLayoutSelection?: boolean; // Allow the user to switch between "top" and "side" layout
  allowThemeSelection?: boolean; // Allow the user to toggle between 'dark' and 'light' mode
  allowTranslate?: boolean; // Allow the user to switch language
  defaultLayout?: AppLayoutMode; // Either "top" (sticky topbar) or "side" (invisible top bar)
  defaultTheme?: PaletteMode; // The default theme of the application.  'dark' or 'light'.
  defaultDrawerOpen?: boolean; // Should the lef nav drawer be opened by default
  defaultShowQuickSearch?: boolean; // Should the quick search be shown by default
  defaultAutoHideAppbar?: boolean; // Should the top bar autohide (applies only to "side" layout)
  defaultShowBreadcrumbs?: boolean; // Indicate whether breadcrumbs should be shown by default.
  topnav?: AppTopNavConfigs; // top nav appbar specific configurations.
  leftnav?: AppLeftNavConfigs; // left nav drawer specific configurations.
  avatarD?: GravatarD; // The gravatar api uses this parameter to generate a themed image unique to an email address.
  notificationURLs?: string[]; // The list of notification URLs.  If no item is provided, the top nav icon is hidden.
};

// Specification interface for the AppProvider's 'theme' attribute.
export type AppThemeConfigs = {
  components?: Components<Omit<Theme, 'components'>>; // Override MaterialUI components styles.
  palette?: AppPaletteConfigs; // MaterialUI theme.palette configuration object.
  appbar?: AppBarThemeConfigs; // Appbar theme/style configuration.
};

// Specification interface for the AppProvider's 'sitemap' attribute.
export type AppSiteMapConfigs = {
  routes: AppSiteMapRoute[]; // The list of application routes.  This is used to match the current route when rendering building and rendering breadcrumbs.
  itemsBefore?: number; // The number of items to show before the ellipsis when breadcrumbs collapses.
  itemsAfter?: number; // The number of itmes to show after the ellipsis when breadcrumbs collapses.
};

// Specification inteface for 'topnav' configurations.
// These configurations apply to the top navigation appbar.
export type AppTopNavConfigs = {
  themeSelectionMode?: AppThemeSelectionMode; // Where does the theme selection menu shows up either. In separate icon ("icon") or under user profile ("profile").
  apps?: AppSwitcherItem[]; // The list of appliations to display in the app-switcher.
  userMenu?: AppBarUserMenuElement[]; // The list of userprofile menu elements.  If no item is provided, the menu is hidden.
  userMenuI18nKey?: string; // (RECOMMENDED) The i18nKey to use to resolve the user menu title.
  userMenuTitle?: string; // Title displayed for the user menu if not using 'userMenuI18nKey' for some reason.
  adminMenu?: AppBarUserMenuElement[]; // The list of userprofile admin menu elements.  If no item is provided, the menu is hidden.
  adminMenuI18nKey?: string; // (RECOMMENDED) The i18nKey to use to resolve the admin menu title.
  adminMenuTitle?: string; // Title displayed for the admin menu
  quickSearchURI?: string; // Uri to redirect to for the appbar quick search.
  quickSearchParam?: string; // Request parameter used to set the quick search query.
  left?: ReactNode; // Top navbar left insertion point for any given component. Component will be inserted at far left (after app title).
  leftAfterBreadcrumbs?: ReactNode; // Top navbar insertion point for any given component.  Component will be inserted after the breadcrumbs.
  rightBeforeSearch?: ReactNode; // Top navbar right insertion point. Component will be inserted before the app search input component.
  right?: ReactNode; // Top navbar insertion point on the right side.  Component will be inserted directly after the app search input comonent.
  hideUserAvatar?: boolean; // Do not show the user profile avatar and menu.
};

// Specification inteface for 'leftnav' configurations.
// These configurations apply to the left navigation drawer.
export type AppLeftNavConfigs = {
  elements: AppLeftNavElement[]; // The list of menu elements in the left navigation drawer
  width?: number; // The the width of the left nav drawer when open.
  hideNestedIcons?: boolean; // Hide the icons for menu items nested within a group
};

// Specification interface to customize default material-ui 'light' and 'dark' themes.
export type AppPaletteConfigs = {
  light?: PaletteOptions; // MaterialUI light theme configuration object.
  dark?: PaletteOptions; // MaterialUI dark theme configuration object
};

export type AppBarThemeConfigs = {
  elevation?: number; // Appbar elevation. Only applies when layout is 'top'.
  light?: AppBarStyles; // Appbar light theme style configuration.
  dark?: AppBarStyles; // Appbar dark theme style configuration.
};

// Specification interface of describing which appbar styles are configurable.
export type AppBarStyles = {
  color?: any; // Configure appbar css color style.
  backgroundColor?: any; // Configure appbar css background color style.
};

// Specification interface describing a sitemap route rendered within breadcrumbs.
export type AppSiteMapRoute = {
  path: string; // The react router path.
  title: string; // The title/label to display when rendering breadcrumb.
  textWidth?: number; // The max width of the text when rendering the breadcrumb.
  icon?: ReactNode; // The icon component to show beside the title/label in breadcrumb.
  isRoot?: boolean; // When true, breadcrumbs will reset to this one path each time it is encountered
  isLeaf?: boolean; // When true, indicates that this path does not aggregate in breadcrumbs.
  exclude?: boolean; // When true, indicates to breadcrumbs component to not render this route.
  breadcrumbs?: string[]; // When specified, the breadcrumbs component will disregard the aggregated list and will use this list of routes instead.
};

// Specification interface for elements of user and admin menus withing the appbar's user profile.
export type AppBarUserMenuElement = {
  i18nKey?: string; // (RECOMMENDED) i18n key used to resolved the elements lable/title.
  title?: string; // The title/label to display when rendering the menu element.
  route?: string; // The route to use when rendering the link component of this menu element.
  icon?: ReactElement<any>; // The icon to render to the left of the title.
  element?: ReactElement<any>; // If specified, will be used to render a profile menu element (takes precedence over [i18nKey, title, route, icon]).
};

// Specification interface describing the type of leftnav menu items to render.
export type AppLeftNavElement = {
  type: 'item' | 'group' | 'divider';
  element: AppLeftNavItem | AppLeftNavGroup | null;
};

// Specification interface of a single leftnav menu item.
export type AppLeftNavItem = {
  id: number | string; // A unique identifer for the item.
  i18nKey?: string; // (RECOMMENDED) i18n key used to resolve item label/text. (Use this if you are dynamically updating the leftnav menu)
  text?: string; // The text/label to use when rendering the item if not using i18nKey (for some reason).
  userPropValidators?: AppUserValidatedProp[]; // The list of user props to assert before rendering the item.
  icon?: ReactElement<any>; // The icon to render to the left of the 'text'.
  route?: string; // If specified, the leftnav item will render a Link component to this route.
  nested?: boolean; // If the item is within a group and rendered as a nested item. (defaults to true)
  render?: (open: boolean) => ReactElement; // If specified, will be used to render the left nav element (takes precendence over [i18nKey, text, icon, route])
};

// Specification interface of a leftnav menu group of items.
export type AppLeftNavGroup = {
  id: number | string; // A unique identifier for the leftnav group.
  open?: boolean; // Indicates whether the leftnav group is open or closed.
  i18nKey?: string; // (RECOMMENDED over 'title') i18n key used to resolve item label/text. (Use this if you are dynamically updating the leftnav menu)
  title?: string; // The text/label to use when rendering the group header if not using i18nKey (for some reason).
  userPropValidators?: AppUserValidatedProp[]; // The list of user props to assert before rendering the item.
  icon: React.ReactElement<any>; // The icon to render on the left of the group header's 'text'
  items: AppLeftNavItem[]; // A list of items to render for this group.
};

// Specification interface for an item provided to the app switcher.
export type AppSwitcherItem = {
  alt: string;
  name: string;
  img_d: React.ReactElement<any> | string;
  img_l: React.ReactElement<any> | string;
  route: string;
  newWindow?: boolean;
};

// Specification type describing the layout supported by the applications.
// 'side' will anchor the leftnav drawer at the same elevation as the appbar and content area (entire height of winddow).
// 'top' will anchor the leftnav drawer under the appbar (which will stick to the top).
export type AppLayoutMode = 'side' | 'top';

// Specification type describing the where to render the theming/preferences options.
// 'profile' will render them under the userprofile menu.
// 'icon' will render a separate icon within which the theming/preferences options will be rendered.
export type AppThemeSelectionMode = 'profile' | 'icon';
