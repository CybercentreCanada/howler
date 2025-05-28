import { AppBreadcrumbsContext } from 'commons/components/app/AppContexts';
import { useContext } from 'react';

export function useAppBreadcrumbs() {
  return useContext(AppBreadcrumbsContext);
}
