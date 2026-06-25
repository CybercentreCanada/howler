import { act, renderHook, waitFor } from '@testing-library/react';
import { useContext, type ReactNode } from 'react';
import { setupContextSelectorMock, setupLocalStorageMock, setupReactRouterMock } from 'tests/mocks';
import { StorageKey } from 'utils/constants';
import GridColumnsProvider, { GridColumnsContext } from './GridColumnsProvider';
import { HitSearchContext, type HitSearchContextType } from './HitSearchProvider';
import { ParameterContext, type ParameterContextType } from './ParameterProvider';
import { ViewContext, type ViewContextType } from './ViewProvider';

setupContextSelectorMock();
setupReactRouterMock();
const mockLocalStorage = setupLocalStorageMock();

import { useParams } from 'react-router-dom';

const mockParams = vi.mocked(useParams);
const mockGetCurrentViews = vi.fn();
const mockSetDisplayType = vi.fn();

const mockViewsContext: Partial<ViewContextType> = {
  getCurrentViews: mockGetCurrentViews
};

const mockHitSearchContext: Partial<HitSearchContextType> = {
  setDisplayType: mockSetDisplayType
};

const makeWrapper = (parameterViewIds: string[] = [], routeId?: string) => {
  mockParams.mockReturnValue({ id: routeId });

  const parameterContextValue: Partial<ParameterContextType> = {
    views: parameterViewIds
  };

  const Wrapper = ({ children }: { children: ReactNode }) => (
    <ParameterContext.Provider value={parameterContextValue as ParameterContextType}>
      <ViewContext.Provider value={mockViewsContext as ViewContextType}>
        <HitSearchContext.Provider value={mockHitSearchContext as HitSearchContextType}>
          <GridColumnsProvider viewSource={routeId ? 'path' : 'params'}>{children}</GridColumnsProvider>
        </HitSearchContext.Provider>
      </ViewContext.Provider>
    </ParameterContext.Provider>
  );

  return Wrapper;
};

const _prefixStorageKey = (key: string) => `howler.ui.${key}`;

describe('no views', () => {
  beforeEach(() => {
    mockLocalStorage.clear();
    mockGetCurrentViews.mockClear();
    mockSetDisplayType.mockClear();

    mockGetCurrentViews.mockResolvedValue([]);

    mockLocalStorage.setItem(_prefixStorageKey(StorageKey.GRID_COLUMNS), JSON.stringify(['col1', 'col2']));
    mockLocalStorage.setItem(_prefixStorageKey(StorageKey.GRID_COLUMN_WIDTHS), JSON.stringify({ col1: '100px' }));
  });

  it('should get columns from local storage', () => {
    const Wrapper = makeWrapper();
    const hook = renderHook(() => useContext(GridColumnsContext), { wrapper: Wrapper });

    expect(mockLocalStorage.getItem).toHaveBeenCalledWith(_prefixStorageKey(StorageKey.GRID_COLUMNS));
    expect(hook.result.current.columns).toEqual(['col1', 'col2']);

    expect(mockLocalStorage.getItem).toHaveBeenCalledWith(_prefixStorageKey(StorageKey.GRID_COLUMN_WIDTHS));
    expect(hook.result.current.columnWidths).toEqual({ col1: 100 });

    expect(mockSetDisplayType).not.toHaveBeenCalled();
  });

  it('should update columns in local storage', () => {
    const Wrapper = makeWrapper();
    const hook = renderHook(() => useContext(GridColumnsContext), { wrapper: Wrapper });

    act(() => {
      hook.result.current.setColumns(['col1', 'col3']);
    });

    expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
      _prefixStorageKey(StorageKey.GRID_COLUMNS),
      JSON.stringify(['col1', 'col3'])
    );
    expect(hook.result.current.columns).toEqual(['col1', 'col3']);
  });

  it('should update column widths in local storage', () => {
    const Wrapper = makeWrapper();
    const hook = renderHook(() => useContext(GridColumnsContext), { wrapper: Wrapper });

    act(() => {
      hook.result.current.setColumnWidth('col1', '150px');
    });

    expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
      _prefixStorageKey(StorageKey.GRID_COLUMN_WIDTHS),
      JSON.stringify({ col1: 150 })
    );
    expect(hook.result.current.columnWidths).toEqual({ col1: 150 });
  });

  it("should add a column width to local storage if it doesn't exist", () => {
    const Wrapper = makeWrapper();
    const hook = renderHook(() => useContext(GridColumnsContext), { wrapper: Wrapper });

    act(() => {
      hook.result.current.setColumnWidth('col2', '200px');
    });

    expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
      _prefixStorageKey(StorageKey.GRID_COLUMN_WIDTHS),
      JSON.stringify({ col1: 100, col2: 200 })
    );
    expect(hook.result.current.columnWidths).toEqual({ col1: 100, col2: 200 });
  });
});

describe('with views', () => {
  const mockViews = new Map([
    [
      'view1',
      {
        view_id: 'view1',
        settings: {
          display: 'grid',
          columns: [
            {
              field: 'viewCol1',
              width: 101
            },
            {
              field: 'viewCol2',
              width: 102
            },
            {
              field: 'viewCol3'
            }
          ]
        }
      }
    ],
    [
      'view2',
      {
        view_id: 'view2',
        settings: {
          display: 'grid',
          columns: [
            {
              field: 'viewCol3',
              width: 103
            },
            {
              field: 'viewCol4',
              width: 204
            },
            {
              field: 'viewCol2',
              width: 202
            }
          ]
        }
      }
    ],
    [
      'view3',
      {
        view_id: 'view3',
        settings: {
          display: 'grid',
          columns: [
            {
              field: 'viewCol5',
              width: 300
            },
            {
              field: 'viewCol6',
              width: 301
            }
          ]
        }
      }
    ],
    ['listView', { view_id: 'listView', settings: { display: 'list' } }]
  ]);

  const getDelayedCurrentViews = (timeout: number) => {
    return ({ views }) =>
      new Promise(resolve =>
        setTimeout(
          () => resolve(views ? views.map((viewId: string) => mockViews.get(viewId)) : Array.from(mockViews.values())),
          timeout
        )
      );
  };
  const localStorageColumns = JSON.stringify(['localCol1', 'localCol2']);
  const localStorageColumnWidths = JSON.stringify({ localCol1: '100px' });

  beforeEach(() => {
    mockLocalStorage.clear();
    mockGetCurrentViews.mockClear();
    mockSetDisplayType.mockClear();

    mockGetCurrentViews.mockImplementation(({ views }) =>
      Promise.resolve(views ? views.map((viewId: string) => mockViews.get(viewId)) : Array.from(mockViews.values()))
    );

    mockLocalStorage.setItem(_prefixStorageKey(StorageKey.GRID_COLUMNS), localStorageColumns);
    mockLocalStorage.setItem(_prefixStorageKey(StorageKey.GRID_COLUMN_WIDTHS), localStorageColumnWidths);
  });

  it('should get columns from parameters', async () => {
    const Wrapper = makeWrapper(['view1', 'view2']);
    const hook = renderHook(() => useContext(GridColumnsContext), { wrapper: Wrapper });

    expect(mockGetCurrentViews).toHaveBeenCalledWith({ views: ['view1', 'view2'] });

    await waitFor(() => expect(hook.result.current.isReady).toBe(true));
    expect(hook.result.current.columns).toEqual(['viewCol1', 'viewCol2', 'viewCol3', 'viewCol4']);
    expect(hook.result.current.columnWidths).toEqual({
      viewCol1: 101,
      viewCol2: 102,
      viewCol4: 204
    });
    expect(mockSetDisplayType).toHaveBeenCalledWith('grid');

    expect(mockLocalStorage.getItem(_prefixStorageKey(StorageKey.GRID_COLUMNS))).toEqual(localStorageColumns);
    expect(mockLocalStorage.getItem(_prefixStorageKey(StorageKey.GRID_COLUMN_WIDTHS))).toEqual(
      localStorageColumnWidths
    );
  });

  it('should get columns from path', async () => {
    const Wrapper = makeWrapper(['view1', 'view2'], 'view3');
    const hook = renderHook(() => useContext(GridColumnsContext), { wrapper: Wrapper });

    expect(mockGetCurrentViews).toHaveBeenCalledWith({ views: ['view3'] });

    await waitFor(() => expect(hook.result.current.isReady).toBe(true));
    expect(hook.result.current.columns).toEqual(['viewCol5', 'viewCol6']);
    expect(hook.result.current.columnWidths).toEqual({ viewCol5: 300, viewCol6: 301 });
    expect(mockSetDisplayType).toHaveBeenCalledWith('grid');

    expect(mockLocalStorage.getItem(_prefixStorageKey(StorageKey.GRID_COLUMNS))).toEqual(localStorageColumns);
    expect(mockLocalStorage.getItem(_prefixStorageKey(StorageKey.GRID_COLUMN_WIDTHS))).toEqual(
      localStorageColumnWidths
    );
  });

  it('should update columns in context', async () => {
    const Wrapper = makeWrapper(['view1']);
    const hook = renderHook(() => useContext(GridColumnsContext), { wrapper: Wrapper });

    await waitFor(() => expect(hook.result.current.isReady).toBe(true));

    await act(async () => {
      hook.result.current.setColumns(['newCol1', 'newCol2']);
    });

    expect(hook.result.current.columns).toEqual(['newCol1', 'newCol2']);
    expect(mockLocalStorage.getItem(_prefixStorageKey(StorageKey.GRID_COLUMNS))).toEqual(localStorageColumns);
    expect(mockLocalStorage.getItem(_prefixStorageKey(StorageKey.GRID_COLUMN_WIDTHS))).toEqual(
      localStorageColumnWidths
    );
  });

  it('should update column widths in context', async () => {
    const Wrapper = makeWrapper(['view1']);
    const hook = renderHook(() => useContext(GridColumnsContext), { wrapper: Wrapper });

    await waitFor(() => expect(hook.result.current.isReady).toBe(true));

    await act(async () => {
      hook.result.current.setColumnWidth('viewCol1', '150px');
    });

    expect(hook.result.current.columnWidths).toEqual({
      viewCol1: 150,
      viewCol2: 102
    });
    expect(mockLocalStorage.getItem(_prefixStorageKey(StorageKey.GRID_COLUMNS))).toEqual(localStorageColumns);
    expect(mockLocalStorage.getItem(_prefixStorageKey(StorageKey.GRID_COLUMN_WIDTHS))).toEqual(
      localStorageColumnWidths
    );
  });

  it("should add a column width to context if it doesn't exist", async () => {
    const Wrapper = makeWrapper(['view1']);
    const hook = renderHook(() => useContext(GridColumnsContext), { wrapper: Wrapper });

    await waitFor(() => expect(hook.result.current.isReady).toBe(true));

    await act(async () => {
      hook.result.current.setColumnWidth('viewCol3', '150px');
    });

    expect(hook.result.current.columnWidths).toEqual({
      viewCol1: 101,
      viewCol2: 102,
      viewCol3: 150
    });
    expect(mockLocalStorage.getItem(_prefixStorageKey(StorageKey.GRID_COLUMNS))).toEqual(localStorageColumns);
    expect(mockLocalStorage.getItem(_prefixStorageKey(StorageKey.GRID_COLUMN_WIDTHS))).toEqual(
      localStorageColumnWidths
    );
  });

  it('should not update context if views change but local edits have been made', async () => {
    // force race condition
    mockGetCurrentViews.mockImplementationOnce(getDelayedCurrentViews(100));

    const Wrapper = makeWrapper(['view1']);
    const hook = renderHook(() => useContext(GridColumnsContext), { wrapper: Wrapper });

    await act(async () => {
      hook.result.current.setColumns(['newCol1', 'newCol2']);
    });

    // dirty takes precedence
    expect(hook.result.current.columns).toEqual(['newCol1', 'newCol2']);
  });

  it('should not update context if async view load returns for an outdated view set', async () => {
    // force race condition
    mockGetCurrentViews.mockImplementationOnce(getDelayedCurrentViews(100));

    const hook = renderHook(() => useContext(GridColumnsContext), { wrapper: makeWrapper([], 'view1') });

    mockParams.mockReturnValue({ id: 'view2' });
    hook.rerender();

    await waitFor(() => expect(hook.result.current.isReady).toBe(true));

    // most recent request takes precedence
    expect(hook.result.current.columns).toEqual(['viewCol3', 'viewCol4', 'viewCol2']);
  });

  it('should keep isReady false until all async view loads are complete', async () => {
    mockGetCurrentViews.mockImplementation(getDelayedCurrentViews(100));
    const hook = renderHook(() => useContext(GridColumnsContext), { wrapper: makeWrapper([], 'view1') });

    mockGetCurrentViews.mockImplementation(getDelayedCurrentViews(200));
    mockParams.mockReturnValue({ id: 'view2' });
    hook.rerender();

    await waitFor(() => expect(hook.result.current.isReady).toBe(true));

    expect(hook.result.current.columns).toEqual(['viewCol3', 'viewCol4', 'viewCol2']);
  });
});
