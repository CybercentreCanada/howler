import api from 'api';
import { useAppUser } from 'commons/components/app/hooks';
import useMyApi from 'components/hooks/useMyApi';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import { has, omit } from 'lodash-es';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { View } from 'models/entities/generated/View';
import { useCallback, useEffect, useState, type FC, type PropsWithChildren } from 'react';
import { useLocation, useParams } from 'react-router-dom';
import { createContext } from 'use-context-selector';
import { StorageKey } from 'utils/constants';

export interface ViewContextType {
  defaultView: string;
  setDefaultView: (viewId: string) => void;
  views: { [viewId: string]: View };
  addFavourite: (id: string) => Promise<void>;
  removeFavourite: (id: string) => Promise<void>;
  fetchViews: (ids?: string[]) => Promise<View[]>;
  addView: (v: View) => Promise<View>;
  editView: (
    id: string,
    title: string,
    query: string,
    sort: string,
    span: string,
    advanceOnTriage: boolean
  ) => Promise<View>;
  removeView: (id: string) => Promise<void>;
  getCurrentView: (lazy?: boolean) => Promise<View>;
}

export const ViewContext = createContext<ViewContextType>(null);

const ViewProvider: FC<PropsWithChildren> = ({ children }) => {
  const { dispatchApi } = useMyApi();
  const appUser = useAppUser<HowlerUser>();
  const [defaultView, setDefaultView] = useMyLocalStorageItem<string>(StorageKey.DEFAULT_VIEW);
  const location = useLocation();
  const routeParams = useParams();

  const [views, setViews] = useState<{ [viewId: string]: View }>({});

  const fetchViews: ViewContextType['fetchViews'] = useCallback(
    async (ids?: string[]) => {
      if (!ids) {
        const newViews = (await dispatchApi(api.view.get(), { throwError: false })) ?? [];

        setViews(_views => ({
          ..._views,
          ...Object.fromEntries(newViews.map(_view => [_view.view_id, _view]))
        }));

        return newViews;
      }

      const missingIds = ids.filter(_id => !views[_id]);

      if (missingIds.length < 1) {
        return ids.map(id => views[id]);
      }

      try {
        const response = await dispatchApi(
          api.search.view.post({
            query: `view_id:(${missingIds.join(' OR ')})`,
            rows: missingIds.length
          })
        );

        const newViews = Object.fromEntries(response.items.map(_view => [_view.view_id, _view]));

        setViews(_views => ({
          ..._views,
          ...Object.fromEntries(missingIds.map(_view_id => [_view_id, null])),
          ...newViews
        }));

        return ids.map(id => views[id] ?? newViews[id]);
      } catch (e) {
        // eslint-disable-next-line no-console
        console.warn(e);

        return [];
      }
    },
    [dispatchApi, views]
  );

  useEffect(() => {
    if (!defaultView || has(views, defaultView)) {
      return;
    }

    (async () => {
      const result = await fetchViews([defaultView]);

      if (!result.length) {
        setDefaultView(undefined);
      }
    })();
  }, [defaultView, fetchViews, setDefaultView, views]);

  const getCurrentView: ViewContextType['getCurrentView'] = useCallback(
    async (lazy = false) => {
      const id = location.pathname.startsWith('/views') ? routeParams.id : defaultView;
      if (!id) {
        return null;
      }

      if (!has(views, id) && !lazy) {
        return (await fetchViews([id]))[0];
      }

      return views[id];
    },
    [defaultView, fetchViews, location.pathname, routeParams.id, views]
  );

  const editView: ViewContextType['editView'] = useCallback(
    async (id: string, title: string, query: string, sort: string, span: string, advanceOnTriage: boolean) => {
      const result = await dispatchApi(api.view.put(id, title, query, sort, span, advanceOnTriage));

      setViews(_views => ({
        ..._views,
        [id]: { ...(_views[id] ?? {}), title, query, sort, span, settings: { advance_on_triage: advanceOnTriage } }
      }));

      return result;
    },
    [dispatchApi]
  );

  const addFavourite: ViewContextType['addFavourite'] = useCallback(
    async (id: string) => {
      await dispatchApi(api.view.favourite.post(id));

      appUser.setUser({
        ...appUser.user,
        favourite_views: [...appUser.user.favourite_views, id]
      });
    },
    [appUser, dispatchApi]
  );

  const addView: ViewContextType['addView'] = useCallback(
    async (view: View) => {
      const newView = await dispatchApi(api.view.post(view));

      setViews(_views => ({ ..._views, [newView.view_id]: newView }));

      addFavourite(newView.view_id);

      return newView;
    },
    [addFavourite, dispatchApi]
  );

  const removeFavourite: ViewContextType['removeFavourite'] = useCallback(
    async (id: string) => {
      await dispatchApi(api.view.favourite.del(id));

      appUser.setUser({
        ...appUser.user,
        favourite_views: appUser.user.favourite_views.filter(v => v !== id)
      });
    },
    [appUser, dispatchApi]
  );

  const removeView: ViewContextType['removeView'] = useCallback(
    async (id: string) => {
      const result = await dispatchApi(api.view.del(id));

      setViews(_views => omit(_views, id));

      if (appUser.user?.favourite_views.includes(id)) {
        removeFavourite(id);
      }

      return result;
    },
    [appUser.user?.favourite_views, dispatchApi, removeFavourite]
  );

  return (
    <ViewContext.Provider
      value={{
        views,
        addFavourite,
        removeFavourite,
        fetchViews,
        addView,
        editView,
        removeView,
        defaultView,
        setDefaultView,
        getCurrentView
      }}
    >
      {children}
    </ViewContext.Provider>
  );
};

export default ViewProvider;
