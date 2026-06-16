import api from 'api';
import { useEffect, useMemo, useState } from 'react';
import { StorageKey } from 'utils/constants';
import useMyApi from './useMyApi';
import { useMyLocalStorageItem } from './useMyLocalStorage';

const useGridColumns = (viewIds?: string[]) => {
  // initialise a column state from the views if they exist, falling back to local storage if not.
  // only updating local storage on changes if there are no views.

  const [localStorageColumns, setLocalStorageColumns] = useMyLocalStorageItem(StorageKey.GRID_COLUMNS, [
    'howler.outline.threat',
    'howler.outline.target',
    'howler.outline.indicators',
    'howler.outline.summary'
  ]);
  const [columns, setColumns] = useState<string[]>(localStorageColumns);

  const { dispatchApi } = useMyApi();
  const idRankMap = useMemo(() => new Map(viewIds?.map((id, index) => [id, index])), [viewIds]);

  useEffect(() => {
    if (viewIds?.length) {
      dispatchApi(api.search.view.post({ query: viewIds.map(viewId => `view_id:${viewId}`).join(' OR ') })).then(
        _response => {
          // collect columns from different views
          const _itemsByPrecedence = _response.items.sort((a, b) => {
            const aRank = idRankMap.get(a.view_id) ?? Infinity;
            const bRank = idRankMap.get(b.view_id) ?? Infinity;
            return aRank === bRank ? 0 : aRank - bRank;
          });
          const _columnMap = new Map<string, { width: number; viewIds: string[] }>();
          const _columns = _itemsByPrecedence.reduce((acc, item) => {
            if (item.settings?.columns) {
              item.settings.columns.forEach(({ field, width }) => {
                // left param precedence for size and ordering
                if (!_columnMap.has(field)) {
                  _columnMap.set(field, { width, viewIds: [item.view_id] });
                  acc.push(field);
                } else {
                  _columnMap.get(field)?.viewIds.push(item.view_id);
                }
              });
            }
            return acc;
          }, [] as string[]);
          if (_columns.length) {
            setColumns(_columns);
          }
        }
      );
    }
  }, [viewIds, idRankMap, dispatchApi]);

  return useMemo(
    () =>
      [
        columns,
        (_columns: string[]) => {
          if (!viewIds?.length) {
            // no views loaded
            setLocalStorageColumns(_columns);
          }
          setColumns(_columns);
        }
      ] as const,
    [columns, setLocalStorageColumns, viewIds]
  );
};

export default useGridColumns;
