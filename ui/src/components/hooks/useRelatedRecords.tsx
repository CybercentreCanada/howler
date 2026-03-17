import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import type { Case } from 'models/entities/generated/Case';
import type { Hit } from 'models/entities/generated/Hit';
import type { Observable } from 'models/entities/generated/Observable';
import type { WithMetadata } from 'models/WithMetadata';
import { useEffect, useState } from 'react';

type MixedRecords = Hit | Observable | Case;

/**
 * Fetches records matching the provided IDs from the hit, observable, and case indexes.
 *
 * @param ids - List of howler.id / case_id values to look up.
 * @param enabled - When false the fetch is skipped (e.g. while a panel is closed).
 */
const useRelatedRecords = <T = MixedRecords,>(ids: string[], enabled = true): WithMetadata<T>[] => {
  const { dispatchApi } = useMyApi();
  const [records, setRecords] = useState<WithMetadata<T>[]>([]);

  useEffect(() => {
    if (!enabled || ids.length === 0) {
      return;
    }

    (async () => {
      const joined = ids.join(' OR ');
      const result = await dispatchApi(
        api.v2.search.post<WithMetadata<T>>('hit,observable,case', {
          query: `howler.id:(${joined}) OR case_id:(${joined})`
        })
      );

      setRecords(result.items);
    })();
  }, [dispatchApi, enabled, ids]);

  return records;
};

export default useRelatedRecords;
