import { useAppUser } from '@tui/core';
import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import { has, omit, uniq } from 'lodash-es';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { View } from 'models/entities/generated/View';
import { useCallback, useEffect, useState, type FC, type PropsWithChildren } from 'react';
import { useSearchParams } from 'react-router';
import { createContext, useContextSelector } from 'use-context-selector';
import { StorageKey } from 'utils/constants';

export interface ViewContextType {
  defaultView: string;
  setDefaultView: (viewId: string | undefined) => void;
  views: { [viewId: string]: View };
  addFavourite: (id: string) => Promise<void>;
  removeFavourite: (id: string) => Promise<void>;
  fetchViews: (ids?: string[]) => Promise<View[]>;
  addView: (v: View) => Promise<View>;
  editView: (id: string, newView: Partial<Omit<View, 'view_id' | 'owner'>>) => Promise<View>;
  removeView: (id: string) => Promise<void>;
  getCurrentViews: (config?: { views?: string[]; lazy?: boolean; ignoreParams?: boolean }) => Promise<View[]>;
}

export const ViewContext = createContext<ViewContextType>(null!);

const ViewProvider: FC<PropsWithChildren> = ({ children }) => {
  const { dispatchApi } = useMyApi();
  const appUser = useAppUser<HowlerUser>();
  const [defaultView, setDefaultViewRaw, removeDefaultView] = useMyLocalStorageItem<string>(StorageKey.DEFAULT_VIEW);
  const setDefaultView = useCallback(
    (viewId: string | undefined) => {
      if (viewId === undefined) {
        removeDefaultView();
      } else {
        setDefaultViewRaw(viewId);
      }
    },
    [removeDefaultView, setDefaultViewRaw]
  );
  const [searchParams] = useSearchParams();

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

      const missingIds = ids.filter(_id => !!_id && !has(views, _id));

      if (missingIds.length < 1) {
        return ids.map(id => views[id]).filter(view => !!view);
      }

      try {
        const response = await dispatchApi(
          api.search.view.post({
            query: `view_id:(${missingIds.join(' OR ')})`,
            rows: missingIds.length,
            sort: 'title asc'
          })
        );

        if (!response) {
          return [];
        }

        const newViews = Object.fromEntries(response.items.map(_view => [_view.view_id, _view]));

        setViews(_views => ({
          ..._views,
          ...newViews
        }));

        return ids.map(id => views[id] ?? newViews[id]).filter(view => !!view);
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

    void (async () => {
      const result = await fetchViews([defaultView]);

      if (!result.length) {
        setDefaultView(undefined);
      }
    })();
  }, [defaultView, fetchViews, setDefaultView, views]);

  const getCurrentViews: ViewContextType['getCurrentViews'] = useCallback(
    async ({ views: _views, lazy = false, ignoreParams = false } = {}) => {
      const currentViews = uniq([...(_views ?? []), ...(ignoreParams ? [] : searchParams.getAll('view'))]);

      if (currentViews.length < 1) {
        return [];
      }

      const results: View[] = [];
      const missing: string[] = [];

      currentViews.forEach(_view => {
        if (has(views, _view)) {
          const view = views[_view];
          if (view) {
            results.push(view);
          }
        } else if (!lazy) {
          missing.push(_view);
        }
      });

      return [...results, ...(await fetchViews(missing))];
    },
    [fetchViews, searchParams, views]
  );

  const editView: ViewContextType['editView'] = useCallback(
    async (id, partialView) => {
      const result = await dispatchApi(api.view.put(id, partialView));
      if (!result) {
        throw new Error(`Unable to update view ${id}.`);
      }

      setViews(_views => ({
        ..._views,
        [id]: { ..._views[id], ...partialView }
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
        favourite_views: [...(appUser.user.favourite_views ?? []), id]
      });
    },
    [appUser, dispatchApi]
  );

  const addView: ViewContextType['addView'] = useCallback(
    async (view: View) => {
      const newView = await dispatchApi(api.view.post(view));
      if (!newView) {
        throw new Error('Unable to create view.');
      }

      const viewId = newView.view_id;
      if (!viewId) {
        throw new Error('Created view did not include an ID.');
      }

      setViews(_views => ({ ..._views, [viewId]: newView }));

      await addFavourite(viewId);

      return newView;
    },
    [addFavourite, dispatchApi]
  );

  const removeFavourite: ViewContextType['removeFavourite'] = useCallback(
    async (id: string) => {
      await dispatchApi(api.view.favourite.del(id));

      appUser.setUser({
        ...appUser.user,
        favourite_views: (appUser.user.favourite_views ?? []).filter(v => v !== id)
      });
    },
    [appUser, dispatchApi]
  );

  const removeView: ViewContextType['removeView'] = useCallback(
    async (id: string) => {
      if (appUser.user?.favourite_views?.includes(id)) {
        await removeFavourite(id);
      }

      await dispatchApi(api.view.del(id));

      setViews(_views => omit(_views, id));
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
        getCurrentViews
      }}
    >
      {children}
    </ViewContext.Provider>
  );
};

export const useViewContextSelector = <Selected,>(selector: (value: ViewContextType) => Selected): Selected => {
  return useContextSelector<ViewContextType, Selected>(ViewContext, selector);
};

export default ViewProvider;
