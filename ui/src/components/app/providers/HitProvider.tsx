import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import { uniq } from 'lodash-es';
import type { Hit } from 'models/entities/generated/Hit';
import type { HitUpdate } from 'models/socket/HitUpdate';
import type { FC, PropsWithChildren } from 'react';
import { useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { createContext } from 'use-context-selector';
import { SocketContext, type RecievedDataType } from './SocketProvider';

interface HitProviderType {
  hits: { [index: string]: Hit };
  selectedHits: Hit[];
  addHitToSelection: (id: string) => void;
  removeHitFromSelection: (id: string) => void;
  clearSelectedHits: (except?: string) => void;
  loadHits: (hits: Hit[]) => void;
  updateHit: (newHit: Hit) => void;
  getHit: (id: string, force?: boolean) => Promise<Hit>;
}

export const HitContext = createContext<HitProviderType>(null);

/**
 * Central repository for storing individual hit data across the application. Allows efficient retrieval of hits across componenents.
 */
const HitProvider: FC<PropsWithChildren> = ({ children }) => {
  const { dispatchApi } = useMyApi();
  const { addListener, removeListener } = useContext(SocketContext);

  /**
   * The most immediate of two levels of caching, this ref stores the raw promises for each hit.
   * Rapidly updates, good for uses in-context where parallel updates my be occurring, i.e.
   * when two cards request the same hit that's missing from the store. Used in getHit for this reason.
   */
  const hitRequests = useRef<{ [id: string]: Promise<Hit> }>({});

  /**
   * The "Authoritative" store of hits. Changes here will trigger rerenders, and essentially
   * caches the result of the above promises. Slower to update, so used outside of the hitcontext
   * where parallel requests aren't an issue.
   */
  const [hits, setHits] = useState<{ [index: string]: Hit }>({});

  const [selectedHitIds, setSelectedHitIds] = useState<string[]>([]);

  // The central location where we propagate any changes from hits made via websockets into the repository. We just save every update,
  // instead of caching it across many components inconsistently as before.
  const handler = useMemo(
    () => (data: RecievedDataType<HitUpdate>) => {
      if (data.hit) {
        // eslint-disable-next-line no-console
        console.debug('Received websocket update for hit', data.hit.howler.id);
        hitRequests.current[data.hit.howler.id] = Promise.resolve(data.hit);
        setHits(_hits => ({ ..._hits, [data.hit.howler.id]: data.hit }));
      }
    },
    []
  );

  useEffect(() => {
    addListener<HitUpdate>('hit_provider', handler);

    return () => removeListener('hit_provider');
  }, [addListener, handler, removeListener]);

  /**
   * A method to retrieve a hit from the context. It first checks the hit state,
   * then checks for ongoing requests, then finally executes a new request if necessary.
   */
  const getHit = useCallback(
    async (id: string, force = false) => {
      if (!hitRequests.current[id] || force) {
        hitRequests.current[id] = dispatchApi(api.hit.get(id));
        const newHit = await hitRequests.current[id];
        setHits(_hits => ({ ..._hits, [id]: newHit }));
      }

      return hitRequests.current[id];
    },
    [dispatchApi]
  );

  /**
   * Update a hit in the context locally
   */
  const updateHit = useCallback((newHit: Hit) => {
    hitRequests.current[newHit.howler.id] = Promise.resolve(newHit);

    setHits(_hits => ({ ..._hits, [newHit.howler.id]: newHit }));
  }, []);

  /**
   * Add a large number of hits to the cache. Used for results of searches.
   */
  const loadHits = useCallback((newHits: Hit[]) => {
    const mappedHits = newHits.map(hit => [hit.howler.id, hit] as [string, Hit]);

    mappedHits.forEach(([id, hit]) => {
      hitRequests.current[id] = Promise.resolve(hit);
    });

    setHits(_hits => ({ ..._hits, ...Object.fromEntries(mappedHits) }));
  }, []);

  const addHitToSelection: HitProviderType['addHitToSelection'] = useCallback((id: string) => {
    setSelectedHitIds(_selected => uniq([..._selected, id]));
  }, []);

  const removeHitFromSelection: HitProviderType['removeHitFromSelection'] = useCallback((id: string) => {
    setSelectedHitIds(_selected => _selected.filter(_id => _id !== id));
  }, []);

  const clearSelectedHits: HitProviderType['clearSelectedHits'] = useCallback((except: string) => {
    setSelectedHitIds(!!except ? [except] : []);
  }, []);

  const selectedHits = useMemo(() => selectedHitIds.map(id => hits[id]).filter(hit => !!hit), [hits, selectedHitIds]);

  useEffect(() => {
    selectedHitIds.forEach(id => {
      if (!hitRequests.current[id]) {
        getHit(id);
      }
    });
  }, [getHit, selectedHitIds]);

  useEffect(() => {
    Object.entries(hits).forEach(([id, hit]) => {
      hitRequests.current[id] = Promise.resolve(hit);
    });
  }, [hits]);

  return (
    <HitContext.Provider
      value={{
        hits,
        getHit,
        updateHit,
        selectedHits,
        addHitToSelection,
        removeHitFromSelection,
        clearSelectedHits,
        loadHits
      }}
    >
      {children}
    </HitContext.Provider>
  );
};

export default HitProvider;
