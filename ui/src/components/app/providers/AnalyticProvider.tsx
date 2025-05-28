import api from 'api';
import type { HowlerSearchResponse } from 'api/search';
import { useAppUser } from 'commons/components/app/hooks';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { Analytic } from 'models/entities/generated/Analytic';
import { createContext, useCallback, useEffect, useState, type FC, type PropsWithChildren } from 'react';
import { sanitizeLuceneQuery } from 'utils/stringUtils';

interface AnalyticContextType {
  ready: boolean;
  analytics: Analytic[];
  addFavourite: (analytic: Analytic) => Promise<void>;
  removeFavourite: (analytic: Analytic) => Promise<void>;
  getIdFromName: (name: string) => Promise<string>;
  getAnalyticFromName: (name: string) => Promise<Analytic>;
  getAnalyticFromId: (id: string) => Promise<Analytic>;
}

export const AnalyticContext = createContext<AnalyticContextType>(null);

/**
 * A set of promises for each analytic search. This is to stop several identical
 * requests from going due to issues with react state updates not happening fast enough
 */
const PROMISES: { [index: string]: Promise<HowlerSearchResponse<Analytic>> } = {};

const AnalyticProvider: FC<PropsWithChildren> = ({ children }) => {
  const appUser = useAppUser<HowlerUser>();
  const [fetching, setFetching] = useState(false);
  const [ready, setReady] = useState(false);
  const [analytics, setAnalytics] = useState<Analytic[]>([]);

  const fetchAnalytics = useCallback(async () => {
    if (ready || fetching) {
      return;
    }

    try {
      setFetching(true);

      setAnalytics(((await api.analytic.get()) ?? []) as Analytic[]);
      setReady(true);
    } finally {
      setFetching(false);
    }
  }, [ready, fetching]);

  useEffect(() => {
    if (!ready && appUser.isReady()) {
      fetchAnalytics();
    }
  }, [ready, appUser, fetchAnalytics]);

  const addFavourite = useCallback(
    async (analytic: Analytic) => {
      await api.analytic.favourite.post(analytic.analytic_id);

      appUser.setUser({
        ...appUser.user,
        favourite_analytics: [...appUser.user.favourite_analytics, analytic.analytic_id]
      });
    },
    [appUser]
  );

  const removeFavourite = useCallback(
    async (analytic: Analytic) => {
      await api.analytic.favourite.del(analytic.analytic_id);

      appUser.setUser({
        ...appUser.user,
        favourite_analytics: appUser.user.favourite_analytics.filter(v => v !== analytic.analytic_id)
      });
    },
    [appUser]
  );

  const getAnalyticFromId = useCallback(
    async (id: string) => {
      const candidate = analytics?.find(_analytic => _analytic.analytic_id === id);
      if (candidate) {
        return candidate;
      }

      // We check to see if there's already a request in progress
      if (!PROMISES[id]) {
        PROMISES[id] = api.search.analytic.post({
          query: `analytic_id:${id}`
        });
      }

      try {
        const result = await PROMISES[id];

        const analytic = result.items?.[0];

        if (analytic) {
          setAnalytics([...(analytics ?? []), analytic]);
          return analytic;
        }
      } catch (e) {
        // eslint-disable-next-line no-console
        console.error(e);
      }

      return null;
    },
    [analytics]
  );

  const getAnalyticFromName = useCallback(
    async (name: string) => {
      const candidate = analytics.find(_analytic => _analytic.name === name);
      if (candidate) {
        return candidate;
      }

      // We check to see if there's already a request in progress
      if (!PROMISES[name]) {
        PROMISES[name] = api.search.analytic.post({
          query: `name:(${sanitizeLuceneQuery(name)})`
        });
      }

      try {
        const result = await PROMISES[name];

        const analytic = result.items?.[0];

        if (analytic) {
          setAnalytics([...analytics, analytic]);
          return analytic;
        }
      } catch (e) {
        // eslint-disable-next-line no-console
        console.error(e);
      }

      return null;
    },
    [analytics]
  );

  const getIdFromName = useCallback(
    async (name: string) => {
      return (await getAnalyticFromName(name))?.analytic_id;
    },
    [getAnalyticFromName]
  );

  return (
    <AnalyticContext.Provider
      value={{ analytics, ready, addFavourite, removeFavourite, getAnalyticFromName, getAnalyticFromId, getIdFromName }}
    >
      {children}
    </AnalyticContext.Provider>
  );
};

export default AnalyticProvider;
