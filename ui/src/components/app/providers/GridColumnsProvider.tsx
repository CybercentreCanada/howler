import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import { createContext, useCallback, useEffect, useMemo, useState } from 'react';
import { useContextSelector } from 'use-context-selector';
import { StorageKey } from 'utils/constants';
import { HitSearchContext } from './HitSearchProvider';
import { ParameterContext } from './ParameterProvider';
import { ViewContext } from './ViewProvider';

export type GridColumnsContextType = {
  columns: string[];
  setColumns: (columns: string[], syncLocal?: boolean) => void;
  columnWidths: Record<string, string>;
  setColumnWidth: (column: string, width: string, syncLocal?: boolean) => void;
  syncToStorage: () => void;
};

export const GridColumnsContext = createContext<GridColumnsContextType>(null);

const GridColumnsProvider = ({ children }) => {
  const viewIds = useContextSelector(ParameterContext, ctx => ctx.views);
  const getCurrentViews = useContextSelector(ViewContext, ctx => ctx.getCurrentViews);
  const setDisplayType = useContextSelector(HitSearchContext, ctx => ctx.setDisplayType);

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
  const [contextColumnMap, setContextColumnMap] = useState<Map<string, { width: string; viewIds: string[] }>>();

  const idRankMap = useMemo(() => new Map(viewIds?.map((id, index) => [id, index])), [viewIds]);

  useEffect(() => {
    getCurrentViews().then(_views => {
      if (_views.length) {
        if (_views[0].settings?.display === 'list') {
          setDisplayType('list');
        } else if (_views[0].settings?.display === 'grid') {
          setDisplayType('grid');

          const _viewsByPrecedence = _views
            .filter(_item => _item.settings?.display === 'grid')
            .sort((a, b) => {
              const aRank = idRankMap.get(a.view_id) ?? Infinity;
              const bRank = idRankMap.get(b.view_id) ?? Infinity;
              return aRank === bRank ? 0 : aRank - bRank;
            });

          const _columnMap = new Map<string, { width: string; viewIds: string[] }>();
          const _columns = _viewsByPrecedence.reduce((acc, item) => {
            if (item.settings?.columns) {
              item.settings.columns.forEach(({ field, width }) => {
                // left param precedence for size and ordering
                if (!_columnMap.has(field)) {
                  _columnMap.set(field, { width: `${width}px`, viewIds: [item.view_id] });
                  acc.push(field);
                } else {
                  _columnMap.get(field)?.viewIds.push(item.view_id);
                }
              });
            }
            return acc;
          }, [] as string[]);

          setContextColumns(_columns);
          setContextColumnMap(_columnMap);
        }
      } else {
        setContextColumns(localStorageColumns);
        setContextColumnMap(null);
      }
    });
  }, [idRankMap, getCurrentViews, localStorageColumns, setDisplayType]);

  const setColumns = useCallback(
    (columns: string[], syncLocal?: boolean) => {
      if (!viewIds?.length || syncLocal) {
        // no views loaded, update the local storage
        setLocalStorageColumns(columns);
      }
      setContextColumns(columns);
    },
    [viewIds, setLocalStorageColumns]
  );

  const columnWidths = useMemo(() => {
    if (contextColumnMap) {
      return Object.fromEntries(
        contextColumns.map(col => {
          const columnSettings = contextColumnMap.get(col);
          return [col, columnSettings?.width ?? null];
        })
      );
    }
    return localStorageColumnWidths;
  }, [contextColumnMap, contextColumns, localStorageColumnWidths]);

  const setColumnWidth = useCallback(
    (column: string, width: string, syncLocal?: boolean) => {
      if (!viewIds?.length || syncLocal) {
        setLocalStorageColumnWidths({
          ...localStorageColumnWidths,
          [column]: width
        });
      }

      const newColumnData = contextColumnMap?.has(column)
        ? { ...contextColumnMap.get(column), width }
        : { width, viewIds: [] };
      setContextColumnMap(new Map(contextColumnMap?.set(column, newColumnData) ?? [[column, newColumnData]]));
    },
    [viewIds, contextColumnMap, localStorageColumnWidths, setLocalStorageColumnWidths]
  );

  const syncToStorage = useCallback(() => {
    setLocalStorageColumns(contextColumns);
    setLocalStorageColumnWidths(columnWidths);
  }, [contextColumns, columnWidths, setLocalStorageColumns, setLocalStorageColumnWidths]);

  return (
    <GridColumnsContext.Provider
      value={{
        columns: contextColumns,
        setColumns,
        columnWidths,
        setColumnWidth,
        syncToStorage
      }}
    >
      {children}
    </GridColumnsContext.Provider>
  );
};

export default GridColumnsProvider;
