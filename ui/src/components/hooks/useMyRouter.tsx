import type { AppBreadcrumbItem, AppRouterAdapter } from '@tui/core';
import { useCallback, useMemo } from 'react';
import { Link, matchPath, useLocation, useMatches, useNavigate, type UIMatch } from 'react-router';

export const useMyRouter = (): AppRouterAdapter => {
  const navigate = useNavigate();
  const matches: UIMatch<any, any>[] = useMatches();
  const location = useLocation();

  const processBreadcrumb = useCallback((match: UIMatch<any, any>): AppBreadcrumbItem[] => {
    const item = match.handle?.breadcrumb ? match.handle.breadcrumb(match) : [];
    return Array.isArray(item) ? item : [item];
  }, []);

  const _matchPath = useCallback((pattern: { path: string; end?: boolean }, pathname: string) => {
    return Boolean(matchPath(pattern, pathname));
  }, []);

  const _breadcrumbs: () => AppBreadcrumbItem[] = useCallback(() => {
    return matches.filter(m => !!m.handle?.breadcrumb).flatMap(m => processBreadcrumb(m));
  }, [matches, processBreadcrumb]);

  return useMemo(
    () => ({
      Link,
      location,
      navigate,
      matchPath: _matchPath,
      breadcrumbs: _breadcrumbs
    }),
    [location, navigate, _breadcrumbs, _matchPath]
  );
};
