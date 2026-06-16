import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import { createContext, useCallback, useEffect, useMemo, useState } from 'react';
import { useContextSelector } from 'use-context-selector';
import { StorageKey } from 'utils/constants';
import { ParameterContext } from './ParameterProvider';

export type GridColumnsContextType = {
  columns: string[];
  setColumns: (columns: string[]) => void;
  columnWidths: Record<string, string>;
  setColumnWidths: (columnWidths: Record<string, string>) => void;
};

export const GridColumnsContext = createContext<GridColumnsContextType>(null);

const GridColumnsProvider = ({ children }) => {
  const viewIds = useContextSelector(ParameterContext, ctx => ctx.views);

  // initialise a column state from the views if they exist, falling back to local storage if not.
  // only updating local storage on changes if there are no views.
  const [localStorageColumns, setLocalStorageColumns] = useMyLocalStorageItem(StorageKey.GRID_COLUMNS, [
    'howler.outline.threat',
    'howler.outline.target',
    'howler.outline.indicators',
    'howler.outline.summary'
  ]);
  const [localStorageColumnWidths, setLocalStorageColumnWidths] = useMyLocalStorageItem<Record<string, string>>(
    StorageKey.GRID_COLUMN_WIDTHS,
    {}
  );
  const [contextColumns, setContextColumns] = useState<string[]>(localStorageColumns);
  const [contextColumnWidths, setContextColumnWidths] = useState<Record<string, string>>(localStorageColumnWidths);

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
            setContextColumns(_columns);
            setContextColumnWidths(_columnWidths =>
              Object.fromEntries(
                _columns.map(col => {
                  const columnSettings = _columnMap.get(col);
                  return [col, columnSettings?.width ? `${columnSettings.width}px` : (_columnWidths[col] ?? null)];
                })
              )
            );
          }
        }
      );
    }
  }, [viewIds, idRankMap, dispatchApi]);

  const setColumns = useCallback(
    (columns: string[]) => {
      if (!viewIds?.length) {
        // no views loaded, update the local storage
        setLocalStorageColumns(columns);
      }
      setContextColumns(columns);
    },
    [viewIds, setLocalStorageColumns]
  );

  const setColumnWidths = useCallback(
    (columnWidths: Record<string, string>) => {
      if (!viewIds?.length) {
        // no views loaded, update the local storage
        setLocalStorageColumnWidths(columnWidths);
      }
      setContextColumnWidths(columnWidths);
    },
    [viewIds, setLocalStorageColumnWidths]
  );

  return (
    <GridColumnsContext.Provider
      value={{
        columns: contextColumns,
        setColumns,
        columnWidths: contextColumnWidths,
        setColumnWidths
      }}
    >
      {children}
    </GridColumnsContext.Provider>
  );
};

export default GridColumnsProvider;
