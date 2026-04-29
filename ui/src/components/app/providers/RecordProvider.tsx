import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import { uniq } from 'lodash-es';
import type { Hit } from 'models/entities/generated/Hit';
import type { Observable } from 'models/entities/generated/Observable';
import type { HitUpdate } from 'models/socket/HitUpdate';
import type { WithMetadata } from 'models/WithMetadata';
import type { FC, PropsWithChildren } from 'react';
import { useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { createContext, useContextSelector } from 'use-context-selector';
import { SocketContext, type RecievedDataType } from './SocketProvider';

export interface RecordContextType {
  records: { [index: string]: Hit | Observable };
  selectedRecords: (Hit | Observable)[];
  addRecordToSelection: (id: string) => void;
  removeRecordFromSelection: (id: string) => void;
  clearSelectedRecords: (except?: string) => void;
  loadRecords: (hits: (Hit | Observable)[]) => void;
  updateRecord: (newHit: Hit | Observable) => void;
  getRecord: (id: string, force?: boolean) => Promise<WithMetadata<Hit | Observable>>;
}

export const RecordContext = createContext<RecordContextType>(null);

/**
 * Central repository for storing individual hit data across the application. Allows efficient retrieval of hits across componenents.
 */
const RecordProvider: FC<PropsWithChildren> = ({ children }) => {
  const { dispatchApi } = useMyApi();
  const { addListener, removeListener } = useContext(SocketContext);

  /**
   * The most immediate of two levels of caching, this ref stores the raw promises for each hit.
   * Rapidly updates, good for uses in-context where parallel updates my be occurring, i.e.
   * when two cards request the same hit that's missing from the store. Used in getRecord for this reason.
   */
  const recordRequests = useRef<{ [id: string]: Promise<Hit | Observable> }>({});

  /**
   * The "Authoritative" store of hits. Changes here will trigger rerenders, and essentially
   * caches the result of the above promises. Slower to update, so used outside of the hitcontext
   * where parallel requests aren't an issue.
   */
  const [records, setRecords] = useState<{ [index: string]: Hit | Observable }>({});

  const [selectedHitIds, setSelectedHitIds] = useState<string[]>([]);

  // The central location where we propagate any changes from hits made via websockets into the repository. We just save every update,
  // instead of caching it across many components inconsistently as before.
  const handler = useMemo(
    () => (data: RecievedDataType<HitUpdate>) => {
      if (data.hit) {
        // eslint-disable-next-line no-console
        console.debug('Received websocket update for hit', data.hit.howler.id);
        recordRequests.current[data.hit.howler.id] = Promise.resolve(data.hit);

        setRecords(_hits => ({
          ..._hits,
          [data.hit.howler.id]: {
            ..._hits[data.hit.howler.id],
            ...data.hit
          }
        }));
      }
    },
    []
  );

  useEffect(() => {
    addListener<HitUpdate>('hits', handler);

    return () => removeListener('hits');
  }, [addListener, handler, removeListener]);

  /**
   * A method to retrieve a record from the context. It first checks the hit state,
   * then checks for ongoing requests, then finally executes a new request if necessary.
   */
  const getRecord = useCallback(
    async (id: string, force = false) => {
      if (!recordRequests.current[id] || force) {
        recordRequests.current[id] = dispatchApi(api.hit.get(id, ['template', 'dossiers', 'analytic', 'overview']));
        const newRecord = await recordRequests.current[id];
        setRecords(_records => ({ ..._records, [id]: newRecord }));
      }

      return recordRequests.current[id];
    },
    [dispatchApi]
  );

  /**
   * Update a hit in the context locally
   */
  const updateRecord = useCallback((newHit: Hit) => {
    recordRequests.current[newHit.howler.id] = Promise.resolve(newHit);

    setRecords(_hits => ({ ..._hits, [newHit.howler.id]: newHit }));
  }, []);

  /**
   * Add a large number of hits to the cache. Used for results of searches.
   */
  const loadRecords = useCallback((newHits: Hit[]) => {
    const mappedHits = newHits.map(hit => [hit.howler.id, hit] as [string, Hit]);

    mappedHits.forEach(([id, hit]) => {
      recordRequests.current[id] = Promise.resolve(hit);
    });

    setRecords(_hits => ({ ..._hits, ...Object.fromEntries(mappedHits) }));
  }, []);

  const addRecordToSelection: RecordContextType['addRecordToSelection'] = useCallback((id: string) => {
    setSelectedHitIds(_selected => uniq([..._selected, id]));
  }, []);

  const removeRecordFromSelection: RecordContextType['removeRecordFromSelection'] = useCallback((id: string) => {
    setSelectedHitIds(_selected => _selected.filter(_id => _id !== id));
  }, []);

  const clearSelectedRecords: RecordContextType['clearSelectedRecords'] = useCallback((except: string) => {
    setSelectedHitIds(!!except ? [except] : []);
  }, []);

  const selectedRecords = useMemo(
    () => selectedHitIds.map(id => records[id]).filter(hit => !!hit),
    [records, selectedHitIds]
  );

  useEffect(() => {
    selectedHitIds.forEach(id => {
      if (!recordRequests.current[id]) {
        getRecord(id);
      }
    });
  }, [getRecord, selectedHitIds]);

  useEffect(() => {
    Object.entries(records).forEach(([id, hit]) => {
      recordRequests.current[id] = Promise.resolve(hit);
    });
  }, [records]);

  return (
    <RecordContext.Provider
      value={{
        records,
        getRecord,
        updateRecord,
        selectedRecords,
        addRecordToSelection,
        removeRecordFromSelection,
        clearSelectedRecords,
        loadRecords
      }}
    >
      {children}
    </RecordContext.Provider>
  );
};

export const useRecordContextSelector = <Selected,>(selector: (value: RecordContextType) => Selected): Selected => {
  return useContextSelector<RecordContextType, Selected>(RecordContext, selector);
};

export default RecordProvider;
