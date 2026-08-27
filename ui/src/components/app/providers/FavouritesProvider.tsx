import { QueryStats, SavedSearch } from '@mui/icons-material';
import type { LeftNavMenuProps, LeftNavRouteProps } from '@tui/core';
import { useAppLeftNav, useAppUser } from '@tui/core';
import { sortBy, uniq } from 'lodash-es';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { MainMenuOperation } from 'plugins/store';
import { createContext, useCallback, useContext, useEffect, type FC, type PropsWithChildren } from 'react';
import { useTranslation } from 'react-i18next';
import { useContextSelector } from 'use-context-selector';
import { applyMainMenuOperations } from 'utils/menuUtils';
import { buildViewUrl } from 'utils/viewUtils';
import { AnalyticContext } from './AnalyticProvider';
import { ViewContext } from './ViewProvider';

export const FavouriteContext = createContext<object>(null);

const FavouriteProvider: FC<PropsWithChildren> = ({ children }) => {
  const { t } = useTranslation();
  const { setMenus } = useAppLeftNav();
  const appUser = useAppUser<HowlerUser>();
  const analytics = useContext(AnalyticContext);
  const userReady = appUser.isReady();
  const favouriteViews = appUser.user?.favourite_views;
  const favouriteAnalytics = appUser.user?.favourite_analytics;

  const fetchViews = useContextSelector(ViewContext, ctx => ctx.fetchViews);

  const processViewMenu = useCallback(async (): Promise<LeftNavMenuProps> => {
    const favourites = uniq(favouriteViews || []);

    if (favourites.length < 1) {
      return null;
    }

    const savedViews = await fetchViews(favourites);

    const items: LeftNavRouteProps[] = sortBy(savedViews, 'title')
      .filter(view => !!view)
      .map(view => ({
        id: view.view_id,
        type: 'route',
        label: t(view.title),
        route: buildViewUrl(view)
      }));

    return {
      id: 'views',
      type: 'menu',
      i18nKey: 'route.views.saved',
      icon: <SavedSearch />,
      items
    };
  }, [favouriteViews, fetchViews, t]);

  const processAnalyticMenu = useCallback((): LeftNavMenuProps => {
    const favourites = favouriteAnalytics;

    if (favourites.length < 1) {
      return null;
    }

    const items: LeftNavRouteProps[] = favourites
      .map(aid => {
        const analytic = analytics.analytics.find(v => v.analytic_id === aid);
        return analytic
          ? {
              id: analytic.analytic_id,
              type: 'route' as const,
              label: t(analytic.name),
              route: `/analytics/${analytic.analytic_id}`
            }
          : null;
      })
      .filter(v => !!v);

    return {
      id: 'analytics',
      type: 'menu',
      i18nKey: 'route.analytics.pinned',
      icon: <QueryStats />,
      items
    };
  }, [analytics.analytics, favouriteAnalytics, t]);

  useEffect(() => {
    if (!userReady || !analytics.ready) {
      return;
    }

    let cancelled = false;

    void (async () => {
      const viewMenu = await processViewMenu();
      if (cancelled) {
        return;
      }

      const analyticMenu = processAnalyticMenu();
      const operations: MainMenuOperation[] = [
        { type: 'remove', targetId: 'views' },
        { type: 'remove', targetId: 'analytics' }
      ];
      let anchorId = 'cases';

      if (viewMenu) {
        operations.push({ type: 'insertRelative', anchorId, position: 'after', item: viewMenu });
        anchorId = viewMenu.id as string;
      }

      if (analyticMenu) {
        operations.push({ type: 'insertRelative', anchorId, position: 'after', item: analyticMenu });
      }

      setMenus(current => current.map(menu => (menu.id === 'root' ? applyMainMenuOperations(menu, operations) : menu)));
    })();

    return () => {
      cancelled = true;
    };
  }, [analytics.ready, processAnalyticMenu, processViewMenu, setMenus, userReady]);

  return <FavouriteContext.Provider value={{}}>{children}</FavouriteContext.Provider>;
};

export default FavouriteProvider;
