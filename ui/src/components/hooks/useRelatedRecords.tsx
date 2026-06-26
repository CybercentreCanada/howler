import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import type { Case } from 'models/entities/generated/Case';
import type { Event } from 'models/entities/generated/Event';
import type { Hit } from 'models/entities/generated/Hit';
import type { WithMetadata } from 'models/WithMetadata';
import { useEffect, useState } from 'react';

type MixedRecords = Hit | Event | Case;

/**
 * Fetches records matching the provided IDs from the hit, event, and case indexes.
 *
 * @param ids - List of howler.id / case_id values to look up.
 * @param enabled - When false the fetch is skipped (e.g. while a panel is closed).
 */
const useRelatedRecords = <T = MixedRecords,>(ids: string[], enabled = true): WithMetadata<T>[] => {
  const { dispatchApi } = useMyApi();
  const [records, setRecords] = useState<WithMetadata<T>[]>([]);

  useEffect(() => {
    if (!enabled || ids.length === 0) {
      if (records.length > 0) {
        setRecords([]);
      }

      return;
    }

    (async () => {
      const joined = ids.join(' OR ');
      const result = await dispatchApi(
        api.v2.search.post<WithMetadata<T>>(['hit', 'event', 'case'], {
          query: `howler.id:(${joined}) OR case_id:(${joined})`
        }),
        { throwError: false, showError: true }
      );

      if (result) {
        setRecords(result.items);
      }
    })();
  }, [dispatchApi, enabled, ids, records.length]);

  return records;
};

export default useRelatedRecords;
