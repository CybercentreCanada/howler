import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import type { View } from 'models/entities/generated/View';
import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
  type SetStateAction
} from 'react';
import { useParams } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import { StorageKey } from 'utils/constants';
import { HitSearchContext } from './HitSearchProvider';
import { ParameterContext } from './ParameterProvider';
import { ViewContext } from './ViewProvider';

export type GridColumnsContextType = {
  columns: string[];
  setColumns: (columns: SetStateAction<string[]>, syncLocal?: boolean) => void;
  columnWidths: Record<string, string>;
  setColumnWidth: (column: string, width: string, syncLocal?: boolean) => void;
  columnSources: Record<string, string[]>;
  syncToStorage: () => void;
  isReady: boolean;
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
  const pathViewIds = useMemo(() => (routeParams.id ? [routeParams.id] : []), [routeParams.id]);
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
  const [isReady, setIsReady] = useState(false);

  const currentLoadRef = useRef({
    viewIds: viewIds,
    hasLocalEdits: false
  });

  const idRankMap = useMemo(() => new Map(viewIds?.map((id, index) => [id, index])), [viewIds]);

  const getViewsByPrecedence = useCallback(
    ({ views }: { views: View[] }) => {
      return views
        .filter(_item => _item.settings?.display === 'grid')
        .sort((a, b) => {
          const aRank = idRankMap.get(a.view_id) ?? Infinity;
          const bRank = idRankMap.get(b.view_id) ?? Infinity;
          return aRank === bRank ? 0 : aRank - bRank;
        });
    },
    [idRankMap]
  );

  const updateContextForViews = useCallback(
    (views: View[]) => {
      if (!views.length) {
        setContextColumns(localStorageColumns);
        setContextColumnMap(null);
        setIsReady(true);
        return;
      }

      if (views[0].settings?.display === 'list') {
        setDisplayType('list');
      } else if (views[0].settings?.display === 'grid') {
        setDisplayType('grid');

        const _viewsByPrecedence = getViewsByPrecedence({ views });
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

      setIsReady(true);
    },
    [getViewsByPrecedence, localStorageColumns, setDisplayType]
  );

  useEffect(() => {
    // Update current load cycle and reset local edits flag when viewIds changes
    currentLoadRef.current = {
      viewIds,
      hasLocalEdits: false
    };

    if (!viewIds?.length) {
      setContextColumns(localStorageColumns);
      setContextColumnMap(null);
      setIsReady(true);
      return;
    }

    setIsReady(false);

    getCurrentViews({ views: viewIds }).then(_views => {
      // only apply results if this is still the current load cycle and no local edits occurred
      if (currentLoadRef.current.hasLocalEdits) {
        setIsReady(true);
        return;
      }

      if (currentLoadRef.current.viewIds === viewIds) {
        updateContextForViews(_views.filter(Boolean));
      }
    });
  }, [viewIds, getCurrentViews, localStorageColumns, updateContextForViews]);

  const setColumns = useCallback(
    (columns: SetStateAction<string[]>, syncLocal?: boolean) => {
      if (!viewIds?.length || syncLocal) {
        const newColumns = typeof columns === 'function' ? columns(contextColumns) : columns;
        setLocalStorageColumns(newColumns);
      }
      // Mark as having local edits so async hydration won't overwrite this change
      currentLoadRef.current.hasLocalEdits = true;
      setContextColumns(columns);
    },
    [viewIds, contextColumns, setLocalStorageColumns]
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
        // Mark as having local edits so async hydration won't overwrite this change
        currentLoadRef.current.hasLocalEdits = true;
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
        syncToStorage,
        isReady
      }}
    >
      {children}
    </GridColumnsContext.Provider>
  );
};

export default GridColumnsProvider;
