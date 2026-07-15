import api from 'api';
import type { Hit } from 'models/entities/generated/Hit';
import type { Overview } from 'models/entities/generated/Overview';
import type { FC, PropsWithChildren } from 'react';
import { createContext, useCallback, useState } from 'react';

interface OverviewContextType {
  overviews: Overview[];
  getOverviews: (force?: boolean) => Promise<Overview[]>;
  getMatchingOverview: (h: Hit) => Overview;
  refresh: () => void;
  loaded: boolean;
}

export const OverviewContext = createContext<OverviewContextType>(null);

const OverviewProvider: FC<PropsWithChildren> = ({ children }) => {
  const [fetching, setFetching] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [overviews, setOverviews] = useState<Overview[]>([]);

  const getOverviews = useCallback(
    async (force = false) => {
      if ((loaded && !force) || fetching) {
        return overviews;
      } else {
        try {
          setFetching(true);

          const result = await api.overview.get();

          setOverviews(result);
          setLoaded(true);

          return result;
        } finally {
          setFetching(false);
        }
      }
    },
    [fetching, loaded, overviews]
  );

  /**
   * Based on a given hit, retrieve the best match for a Overview
   */
  const getMatchingOverview = useCallback(
    (hit: Hit) =>
      hit &&
      overviews
        .filter(
          _overview =>
            // The analytic must match, and the detection must either a) not exist or b) match the hit
            _overview.analytic === hit.howler.analytic &&
            (!_overview.detection || _overview.detection.toLowerCase() === hit.howler.detection?.toLowerCase())
        )
        .sort((a, b) => {
          if (a.detection && !b.detection) {
            return -1;
          } else if (!a.detection && b.detection) {
            return 1;
          } else {
            return 0;
          }
        })[0],
    [overviews]
  );

  const refresh = useCallback(() => {
    setLoaded(false);
    getOverviews();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <OverviewContext.Provider
      value={{
        overviews,
        getOverviews,
        getMatchingOverview,
        refresh,
        loaded
      }}
    >
      {children}
    </OverviewContext.Provider>
  );
};

export default OverviewProvider;
