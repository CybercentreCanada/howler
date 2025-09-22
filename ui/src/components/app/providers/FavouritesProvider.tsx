import { QueryStats, SavedSearch } from '@mui/icons-material';
import type { AppLeftNavElement, AppLeftNavGroup } from 'commons/components/app/AppConfigs';
import { useAppLeftNav, useAppUser } from 'commons/components/app/hooks';
import { sortBy, uniq } from 'lodash-es';
import type { HowlerUser } from 'models/entities/HowlerUser';
import { createContext, useCallback, useContext, useEffect, type FC, type PropsWithChildren } from 'react';
import { useTranslation } from 'react-i18next';
import { useContextSelector } from 'use-context-selector';
import { AnalyticContext } from './AnalyticProvider';
import { ViewContext } from './ViewProvider';

export const FavouriteContext = createContext<object>(null);

const FavouriteProvider: FC<PropsWithChildren> = ({ children }) => {
  const { t } = useTranslation();
  const leftNav = useAppLeftNav();
  const appUser = useAppUser<HowlerUser>();
  const analytics = useContext(AnalyticContext);

  const fetchViews = useContextSelector(ViewContext, ctx => ctx.fetchViews);

  const processViewElement = useCallback(async (): Promise<AppLeftNavElement> => {
    const viewElement = leftNav.elements.find(el => el.element?.id === 'views');
    const favourites = uniq(appUser.user?.favourite_views || []);

    // There are no favourites and no nav elements - return
    if (favourites.length < 1 && !viewElement) {
      return null;
    }

    // There are no favourites, but the nav element exists - remove it
    if (favourites.length < 1) {
      return null;
    }

    // The favourite list is fully represented, skip
    if (favourites.length === (viewElement?.element as AppLeftNavGroup)?.items?.length) {
      return viewElement;
    }

    const savedViews = await fetchViews(favourites);

    const items = sortBy(savedViews, 'title')
      .filter(view => !!view)
      .map(view => ({
        id: view.view_id,
        text: t(view.title),
        route: `/views/${view.view_id}`,
        nested: true
      }));

    if (viewElement) {
      const newViewElement = {
        ...viewElement,
        element: {
          ...viewElement.element,
          items
        }
      };

      return newViewElement;
    } else {
      return {
        type: 'group',
        element: {
          id: 'views',
          i18nKey: 'route.views.saved',
          icon: <SavedSearch />,
          items
        }
      };
    }
  }, [appUser.user?.favourite_views, fetchViews, leftNav.elements, t]);

  const processAnalyticElement = useCallback((): AppLeftNavElement => {
    const analyticElement = leftNav.elements.find(el => el.element?.id === 'analytics');
    const favourites = appUser.user?.favourite_analytics;

    // There are no favourites and no nav elements - return
    if (favourites.length < 1 && !analyticElement) {
      return null;
    }

    // There are no favourites, but the nav element exists - remove it
    if (favourites.length < 1) {
      return null;
    }

    // The favourite list is fully represented, skip
    if (favourites.length === (analyticElement?.element as AppLeftNavGroup)?.items?.length) {
      return analyticElement;
    }

    const items = favourites
      .map(aid => {
        const analytic = analytics.analytics.find(v => v.analytic_id === aid);
        return analytic
          ? {
              id: analytic.analytic_id,
              text: t(analytic.name),
              route: `/analytics/${analytic.analytic_id}`,
              nested: true
            }
          : null;
      })
      .filter(v => !!v);

    if (analyticElement) {
      return {
        ...analyticElement,
        element: {
          ...analyticElement.element,
          items
        }
      };
    } else {
      return {
        type: 'group',
        element: {
          id: 'analytics',
          i18nKey: 'route.analytics.pinned',
          icon: <QueryStats />,
          items
        }
      };
    }
  }, [analytics.analytics, appUser.user?.favourite_analytics, leftNav, t]);

  useEffect(() => {
    if (!appUser.isReady() || !analytics.ready) {
      return;
    }

    const newElements = leftNav.elements
      .filter(el => !['views', 'analytics'].includes(el.element?.id as any))
      .filter(el => !!el);

    (async () => {
      const analyticElement = processAnalyticElement();
      if (analyticElement) {
        newElements.splice(1, 0, analyticElement);
      }

      const viewElement = await processViewElement();
      if (viewElement) {
        newElements.splice(1, 0, viewElement);
      }

      leftNav.setElements(newElements);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analytics.ready, appUser]);

  return <FavouriteContext.Provider value={{}}>{children}</FavouriteContext.Provider>;
};

export default FavouriteProvider;
