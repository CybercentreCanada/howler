import type { PaletteMode } from '@mui/material';
import type { AppConfigs, AppLayoutMode, AppLeftNavElement, AppSwitcherItem } from 'commons/components/app/AppConfigs';
import type { ItemComponentProps } from 'commons/components/app/AppNotificationService';
import type { AppSearchItem, AppSearchMode, AppSearchService } from 'commons/components/app/AppSearchService';
import type { AppUser, AppUserService } from 'commons/components/app/AppUserService';
import type { BreadcrumbItem } from 'commons/components/app/hooks/useAppSitemap';
import { createContext, type ReactElement } from 'react';

export type AppContextType = {
  // configs as provided by client application.
  configs: AppConfigs; // app specific configurations.
  theme: PaletteMode; // provided theme config.
  toggleTheme: () => void; // toggle between light/dark theme mode.
  toggleLanguage: () => void; // toggle between french/english language.
};

export type AppSwitcherContextType = {
  empty: boolean; // is the items list empty?
  items: AppSwitcherItem[]; // the items to render in the app switcher.
  setItems: (items: AppSwitcherItem[]) => void; // updates the items rendered by the app switcher.
};

export type AppQuickSearchContextType = {
  show: boolean; // is the quick search shown in the app bar?
  setShow: (show: boolean) => void; // specify whether to show the quick search in the app bar.
  toggle: () => void; // hide/show the quick search in the app bar.
};

export type AppSearchServiceContextType<T = any> = {
  provided: boolean; // has a search service been provided? - if false, then it means the default service is being used.
  service: AppSearchService<T>; // the search service implementation to use.
  state: AppSearchServiceState<T>; // the state of the search service.
};

export type AppNotificationServiceContextType = {
  provided: boolean; // has a search service been provided? - if false, then it means the default service is being used.
  service: AppNotificationService; // the search service implementation to use.
  state: AppNotificationServiceState; // the state of the search service.
};

export type AppLeftNavContextType = {
  open: boolean; // left nav is open/expanded?
  elements: AppLeftNavElement[]; // the elements to render in the left nav.
  toggle: () => void; // minimize/expand left nav.
  setOpen: (show: boolean) => void; // specify whether the left nav should be expanded[true] or minimized[false]
  setElements: (elements: AppLeftNavElement[]) => void; // specify the elements to render in the left nav.
};

export type AppLayoutContextType = {
  ready: boolean; // is the layout ready?
  current: AppLayoutMode; // the current mode of the layout ['side' | 'top].
  hideMenus: () => void; // hide the left nav menu and the app bar.
  setReady: (ready: boolean) => void; // specifiy whether the applayout is ready to render.
  toggle: () => void; // toggle between 'top' and 'side' layout mode.
};

export type AppBarContextType = {
  show: boolean; // is the appbar shown?
  autoHide: boolean; // is the appbar auto hiding on scroll or being sticky?
  setShow: (show: boolean) => void; // specify whether to show the app bar or not.
  setAutoHide: (autoHide: boolean) => void; // specify whether to auto hide the app bar.
  toggleAutoHide: () => void; // toggle the auto hide property.
};

export type AppBreadcrumbsContextType = {
  show: boolean; // are the breadcrumbs shown?
  items: BreadcrumbItem[]; // the items to render in the breadcrumbs.
  setItems: (newItems: BreadcrumbItem[]) => void; // Set the list of breadcrumbs manually
  toggle: () => void; // show/hide the breadcrumbs.
  last: () => BreadcrumbItem; // the first item in the breacrumbs.
  first: () => BreadcrumbItem; // the last item in the breadcrumbs.
};

export type AppDrawerContextType = {
  isOpen: boolean;
  isFloatThreshold: boolean;
  width: number | string;
  maximized: boolean;
  element: ReactElement;
  open: (props: AppDrawerOpenProps) => void;
  close: () => void;
  setWidth: (width: number | string) => void;
  setMaximized: (maximized: boolean) => void;
};

export type AppSearchServiceState<T = any, R = any> = {
  searching: boolean; // indicates if the app search should show the progress indicator.
  menu: boolean; // is the app search result menu opened?
  mode: AppSearchMode; // inline vs fullscreen.
  items: AppSearchItem<T>[]; // the app search result items to render.
  result?: R; // any object, metadata related to the search result.
  set: (state: AppSearchServiceState<T>) => void; // update app search state.
};

//NotificationState is only used if feedUrls is empty
export type AppNotificationServiceState = {
  urls: string[]; // The feed urls
  set: (state: AppNotificationServiceState) => void; // Update the feed urls from the state
};

export type AppNotificationService = {
  feedUrls?: string[]; // Static urls can be provided at initialization or see state object (AppNotificationServiceState)
  notificationRenderer?: (item: ItemComponentProps) => ReactElement; // Cusotm component for notification rendering
};

// Specification interface of the AppDrawer's 'open' method arguments object.
export type AppDrawerOpenProps = {
  element: ReactElement;
  width?: number | string;
  floatThreshold?: number;
  onClose?: (action: 'close' | 'hide') => void;
};

// React Context for the AppProvider (Root Context).
export const AppContext = createContext<AppContextType>(null);

// React Context for the AppLayoutProvider.
export const AppLayoutContext = createContext<AppLayoutContextType>(null);

// React Context for the AppBarProvider.
export const AppBarContext = createContext<AppBarContextType>(null);

// React Context for the AppBreadcrumbsProvider.
export const AppBreadcrumbsContext = createContext<AppBreadcrumbsContextType>(null);

// React Context for the AppLeftNavProvider.
export const AppLeftNavContext = createContext<AppLeftNavContextType>(null);

// React Context for the AppQuickSearchProvider.
export const AppQuickSearchContext = createContext<AppQuickSearchContextType>(null);

// React Context for the AppSearchServiceProvider.
export const AppSearchServiceContext = createContext<AppSearchServiceContextType>(null);

// React Context for the AppSwitcherProvider.
export const AppSwitcherContext = createContext<AppSwitcherContextType>(null);

// React Context for the AppUserProvider.
export const AppUserContext = createContext<AppUserService<AppUser>>(null);

// React Context for the AppNotificationServiceProvider.
export const AppNotificationServiceContext = createContext<AppNotificationServiceContextType>(null);
