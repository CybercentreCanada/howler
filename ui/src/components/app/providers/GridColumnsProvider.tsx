import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import { createContext, useCallback, useEffect, useMemo, useState, type PropsWithChildren } from 'react';
import { useParams } from 'react-router-dom';
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
  columnSources: Record<string, string[]>;
  syncToStorage: () => void;
};

export const GridColumnsContext = createContext<GridColumnsContextType>(null);

const GridColumnsProvider = ({
  children,
  viewSource = 'params'
}: PropsWithChildren<{ viewSource?: 'params' | 'path' }>) => {
  // initialise a column state from the views if they exist, falling back to local storage if not.
  // only updating local storage on changes if there are no views.

  const routeParams = useParams();

  const parameterViewIds = useContextSelector(ParameterContext, ctx => ctx.views);
  const pathViewIds = useMemo(() => [routeParams.id], [routeParams.id]);
  const viewIds = viewSource === 'params' ? parameterViewIds : pathViewIds;

  const getCurrentViews = useContextSelector(ViewContext, ctx => ctx.getCurrentViews);
  const setDisplayType = useContextSelector(HitSearchContext, ctx => ctx.setDisplayType);

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
  const [contextColumnMap, setContextColumnMap] = useState<Map<string, { width: string; viewTitles: string[] }>>();

  const idRankMap = useMemo(() => new Map(viewIds?.map((id, index) => [id, index])), [viewIds]);

  useEffect(() => {
    getCurrentViews({ views: viewIds }).then(_views => {
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

          const _columnMap = new Map<string, { width: string; viewTitles: string[] }>();
          const _columns = _viewsByPrecedence.reduce((acc, item) => {
            if (item.settings?.columns) {
              item.settings.columns.forEach(({ field, width }) => {
                // left param precedence for size and ordering
                if (!_columnMap.has(field)) {
                  _columnMap.set(field, { width: width ? `${width}px` : undefined, viewTitles: [item.title] });
                  acc.push(field);
                } else {
                  _columnMap.get(field)?.viewTitles.push(item.title);
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
  }, [viewIds, idRankMap, getCurrentViews, localStorageColumns, setDisplayType]);

  const setColumns = useCallback(
    (columns: string[], syncLocal?: boolean) => {
      if (!viewIds?.length || syncLocal) {
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
          return [col, columnSettings?.width];
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
      } else {
        setContextColumnMap(_contextColumnMap => {
          const newColumnData = _contextColumnMap?.has(column)
            ? { ..._contextColumnMap.get(column), width }
            : { width, viewTitles: [] };

          return new Map(_contextColumnMap?.set(column, newColumnData) ?? [[column, newColumnData]]);
        });
      }
    },
    [viewIds, localStorageColumnWidths, setLocalStorageColumnWidths]
  );

  const columnSources = useMemo(() => {
    if (!contextColumns) {
      return {};
    }

    return Object.fromEntries(
      contextColumns.map(col => {
        const columnSettings = contextColumnMap?.get(col);
        return [col, columnSettings?.viewTitles ?? []];
      })
    );
  }, [contextColumnMap, contextColumns]);

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
        columnSources,
        syncToStorage
      }}
    >
      {children}
    </GridColumnsContext.Provider>
  );
};

export default GridColumnsProvider;
