import type { TuiCookies } from '@tui/core';

export const APP_COOKIES_DEFAULTS: Partial<TuiCookies> = {
  showBreadcrumbs: false,
  showQuickSearch: false,
  drawerOpen: true
};

export const useMyCookies = () => {
  return APP_COOKIES_DEFAULTS;
};
