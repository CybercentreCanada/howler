import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
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
import { parsePixelSizeStringToInt } from 'utils/stringUtils';
import { HitSearchContext } from './HitSearchProvider';
import { ParameterContext } from './ParameterProvider';
import { ViewContext } from './ViewProvider';

/**
 * Shape of the context value exposed by {@link GridColumnsProvider}.
 *
 * Column state is sourced from active views when present, otherwise from local storage.
 * Mutations follow the same rule: they write back to local storage only when there are no
 * active views (or when `syncLocal` is explicitly set to `true`).
 */
export type GridColumnsContextType = {
  /** Ordered list of field keys to display as grid columns. */
  columns: string[];
  /**
   * Replace or update the active column list.
   * @param syncLocal - When `true`, also persists the change to local storage even if views are active.
   */
  setColumns: (columns: SetStateAction<string[]>, syncLocal?: boolean) => void;
  /** Per-column widths (pixels, e.g. `120`), keyed by field name. */
  columnWidths: Record<string, number>;
  /**
   * Set the width of a single column.
   * @param syncLocal - When `true`, also persists the change to local storage even if views are active.
   */
  setColumnWidth: (column: string, width: number, syncLocal?: boolean) => void;
  /**
   * Maps each column field to the list of view titles that declared it.
   * Empty array for columns that came from local storage rather than a view.
   */
  columnSources: Record<string, string[]>;
  /** Persist the current in-memory column configuration (columns + widths) to local storage. */
  syncToStorage: () => void;
  /** `false` while an async view fetch is in flight; `true` once the column state is settled. */
  isReady: boolean;
};

export const GridColumnsContext = createContext<GridColumnsContextType>(null);

/**
 * Manages which grid columns are active and how wide they are.
 *
 * **Priority order:**
 * 1. Active views (fetched asynchronously) — columns and widths are derived from view settings.
 * 2. Local storage — used as fallback when no views are active.
 *
 * Local storage is only written when there are no active views, keeping view-driven state
 * isolated from the user's personal preferences.
 *
 * @param viewSource - Determines where view IDs are read from:
 *   - `"params"` (default) — reads from `ParameterContext` (query-string driven).
 *   - `"path"` — reads from the current route's `:id` param.
 */
const GridColumnsProvider = ({
  children,
  viewSource = 'params'
}: PropsWithChildren<{ viewSource?: 'params' | 'path' }>) => {
  const routeParams = useParams();

  // Resolve view IDs from the appropriate source.
  const parameterViewIds = useContextSelector(ParameterContext, ctx => ctx.views);
  const pathViewIds = useMemo(() => (routeParams.id ? [routeParams.id] : []), [routeParams.id]);
  const viewIds = viewSource === 'params' ? parameterViewIds : pathViewIds;

  const getCurrentViews = useContextSelector(ViewContext, ctx => ctx.getCurrentViews);
  const setDisplayType = useContextSelector(HitSearchContext, ctx => ctx.setDisplayType);

  // --- Local storage state (user's personal preferences) ---
  const [localStorageColumns, setLocalStorageColumns] = useMyLocalStorageItem(StorageKey.GRID_COLUMNS, [
    'howler.outline.threat',
    'howler.outline.target',
    'howler.outline.indicators',
    'howler.outline.summary'
  ]);
  const [localStorageColumnWidths, setLocalStorageColumnWidths] = useMyLocalStorageItem<
    Record<string, string | number>
  >(StorageKey.GRID_COLUMN_WIDTHS, {});

  // --- In-memory state (may be overridden by view data) ---
  const [contextColumns, setContextColumns] = useState<string[]>(localStorageColumns);
  /** Non-null only when columns were loaded from views; null means fall back to local storage widths. */
  const [viewColumnWidths, setViewColumnWidths] = useState<Record<string, number> | null>(null);
  /** Non-null only when columns were loaded from views; tracks which view(s) declared each column. */
  const [viewColumnSources, setViewColumnSources] = useState<Record<string, string[]> | null>(null);
  const [isReady, setIsReady] = useState(false);

  // Parse local storage widths into numbers for backwards compatibility with css style strings
  const parsedLocalStorageColumnWidths = useMemo(() => {
    const parsed: Record<string, number> = {};
    for (const [col, width] of Object.entries(localStorageColumnWidths)) {
      const numWidth = typeof width === 'string' ? parsePixelSizeStringToInt(width) : width;
      if (numWidth !== null) {
        parsed[col] = numWidth;
      }
    }
    return parsed;
  }, [localStorageColumnWidths]);

  /**
   * Tracks the current async load "cycle" to guard against stale async results.
   * - `viewIds` is snapshotted at the start of each effect run; the callback checks
   *   identity (`===`) before applying results to confirm it is still the current run.
   * - `hasLocalEdits` is set to `true` the moment the user makes a manual change mid-flight,
   *   which causes the pending async response to be discarded.
   */
  const currentLoadRef = useRef({ viewIds, hasLocalEdits: false });
  const hasViews = viewIds?.length > 0;

  // Fetch and apply view column settings whenever the set of active views changes.
  useEffect(() => {
    // Start a new load cycle.
    currentLoadRef.current = { viewIds, hasLocalEdits: false };

    if (!hasViews) {
      // No views active — fall back to local storage immediately.
      setContextColumns(localStorageColumns);
      setViewColumnWidths(null);
      setViewColumnSources(null);
      setIsReady(true);
      return;
    }

    setIsReady(false);

    void getCurrentViews({ views: viewIds }).then(_views => {
      // Discard stale results: either the user already made a manual edit, or viewIds changed.
      if (currentLoadRef.current.hasLocalEdits) {
        setIsReady(true);
        return;
      }

      if (currentLoadRef.current.viewIds !== viewIds) {
        return;
      }

      const views = _views.filter(Boolean);

      if (!views.length) {
        // Views resolved to nothing (e.g. all deleted) — fall back to local storage.
        setContextColumns(localStorageColumns);
        setViewColumnWidths(null);
        setViewColumnSources(null);
        setIsReady(true);
        return;
      }

      // Honour the display-type declared by the highest-priority view.
      if (views[0].settings?.display === 'list') {
        setDisplayType('list');
      } else if (views[0].settings?.display === 'grid') {
        setDisplayType('grid');

        // Sort grid views by their position in the requested viewIds array so that
        // the first-listed view has the highest precedence for column order and width.
        const idRankMap = new Map(viewIds.map((id, i) => [id, i]));
        const gridViews = views
          .filter(v => v.settings?.display === 'grid')
          .sort((a, b) => (idRankMap.get(a.view_id) ?? Infinity) - (idRankMap.get(b.view_id) ?? Infinity));

        const columns: string[] = [];
        const widths: Record<string, number> = {};
        const sources: Record<string, string[]> = {};

        for (const view of gridViews) {
          for (const { field, width } of view.settings?.columns ?? []) {
            if (!sources[field]) {
              // First occurrence wins for column order and width.
              columns.push(field);
              widths[field] = width ?? undefined;
              sources[field] = [view.title];
            } else {
              // Subsequent views that also declare this field are recorded as additional sources.
              sources[field].push(view.title);
            }
          }
        }

        setContextColumns(columns);
        setViewColumnWidths(widths);
        setViewColumnSources(sources);
      }

      setIsReady(true);
    });
    // oxlint-disable-next-line react-hooks/exhaustive-deps
  }, [viewIds, hasViews, getCurrentViews, localStorageColumns, setDisplayType]);

  const setColumns = useCallback(
    (columns: SetStateAction<string[]>, syncLocal?: boolean) => {
      // Persist to local storage only when there are no active views (or when explicitly requested).
      if (!hasViews || syncLocal) {
        const newColumns = typeof columns === 'function' ? columns(contextColumns) : columns;
        setLocalStorageColumns(newColumns);
      }
      // Flag that a user edit has occurred so any in-flight async fetch won't overwrite this change.
      currentLoadRef.current.hasLocalEdits = true;
      setContextColumns(columns);
    },
    [hasViews, contextColumns, setLocalStorageColumns]
  );

  // When views are active, use their widths; otherwise fall back to local storage widths.
  const columnWidths = useMemo(
    () => viewColumnWidths ?? parsedLocalStorageColumnWidths,
    [viewColumnWidths, parsedLocalStorageColumnWidths]
  );

  const setColumnWidth = useCallback(
    (column: string, width: number, syncLocal?: boolean) => {
      if (!hasViews || syncLocal) {
        // No active views — persist directly to local storage.
        setLocalStorageColumnWidths({ ...parsedLocalStorageColumnWidths, [column]: width });
      } else {
        // Active views — update the in-memory view widths only, and flag a local edit.
        currentLoadRef.current.hasLocalEdits = true;
        setViewColumnWidths(prev => ({ ...prev, [column]: width }));
      }
    },
    [hasViews, parsedLocalStorageColumnWidths, setLocalStorageColumnWidths]
  );

  // Map each column to the view(s) that declared it, or an empty array for local-storage columns.
  const columnSources = useMemo(
    () => Object.fromEntries(contextColumns.map(col => [col, viewColumnSources?.[col] ?? []])),
    [viewColumnSources, contextColumns]
  );

  /** Flush the current in-memory state to local storage (used by the "save to storage" action). */
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
