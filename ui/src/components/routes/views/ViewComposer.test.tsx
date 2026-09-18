/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockShowSuccessMessage = vi.hoisted(() => vi.fn());
const mockShowErrorMessage = vi.hoisted(() => vi.fn());
const mockNavigate = vi.hoisted(() => vi.fn());
const mockAddView = vi.hoisted(() => vi.fn());
const mockEditView = vi.hoisted(() => vi.fn());
const mockGetCurrentViews = vi.hoisted(() => vi.fn());
const mockLoadRecords = vi.hoisted(() => vi.fn());

const viewContextToken = vi.hoisted(() => ({ name: 'view-context' }));
const parameterContextToken = vi.hoisted(() => ({ name: 'parameter-context' }));
const recordContextToken = vi.hoisted(() => ({ name: 'record-context' }));
const recordSearchContextToken = vi.hoisted(() => ({ name: 'record-search-context' }));
const gridColumnsContextToken = vi.hoisted(() => ({ name: 'grid-columns-context' }));

let routeParamsValue: any = {};
let parameterContextValue: any;
let recordSearchContextValue: any;
let gridColumnsContextValue: any;
let searchResponseValue: any;

vi.mock('@mui/icons-material', () => ({
  HelpOutline: () => <div>help-icon</div>,
  Save: () => <div>save-icon</div>,
  Settings: () => <div>settings-icon</div>
}));

vi.mock('@mui/material', () => ({
  Alert: ({ children }: any) => <div>{children}</div>,
  Checkbox: ({ checked, onChange }: any) => (
    <button onClick={() => onChange?.(null, !checked)}>{checked ? 'checked' : 'unchecked'}</button>
  ),
  CircularProgress: () => <div>loading</div>,
  LinearProgress: () => <div>progress</div>,
  Paper: ({ children }: any) => <div>{children}</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  TextField: ({ label, value, onChange }: any) => (
    <label>
      {label}
      <input aria-label={label} value={value} onChange={onChange} />
    </label>
  ),
  ToggleButton: ({ children, value }: any) => <button data-value={value}>{children}</button>,
  ToggleButtonGroup: ({ children, onChange }: any) => (
    <div>
      <button onClick={() => onChange?.(null, 'personal')}>switch-personal</button>
      {children}
    </div>
  ),
  Tooltip: ({ children }: any) => <>{children}</>,
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('@tui/core', () => ({
  AppListEmpty: () => <div>empty-list</div>,
  PageCenter: ({ children }: any) => <div>{children}</div>
}));

vi.mock('api', () => ({
  default: {
    v2: {
      search: {
        post: (indexes: string[], body: any) => ({ indexes, body })
      }
    }
  }
}));

vi.mock('components/app/providers/GridColumnsProvider', () => ({
  GridColumnsContext: gridColumnsContextToken
}));

vi.mock('components/app/providers/ParameterProvider', () => ({
  ParameterContext: parameterContextToken
}));

vi.mock('components/app/providers/RecordProvider', () => ({
  RecordContext: recordContextToken
}));

vi.mock('components/app/providers/RecordSearchProvider', () => ({
  RecordSearchContext: recordSearchContextToken
}));

vi.mock('components/app/providers/ViewProvider', () => ({
  ViewContext: viewContextToken
}));

vi.mock('components/elements/addons/buttons/CustomButton', () => ({
  default: ({ children, onClick, disabled }: any) => <button onClick={onClick} disabled={disabled}>{children}</button>
}));

vi.mock('components/elements/addons/layout/FlexOne', () => ({
  default: () => <div>flex</div>
}));

vi.mock('components/elements/addons/layout/FlexPort', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/elements/addons/layout/vsbox/VSBox', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/elements/addons/layout/vsbox/VSBoxContent', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/elements/addons/layout/vsbox/VSBoxHeader', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/elements/addons/search/SearchTotal', () => ({
  default: ({ total, pageLength, offset }: any) => <div>{`total:${total}:${pageLength}:${offset}`}</div>
}));

vi.mock('components/elements/display/ChipPopper', () => ({
  default: ({ children, label }: any) => <div>{label}{children}</div>
}));

vi.mock('components/elements/event/EventCard', () => ({
  default: ({ event }: any) => <div>{`event:${event.howler.id}`}</div>
}));

vi.mock('components/elements/hit/grid/AddColumnModal', () => ({
  default: ({ addColumn }: any) => <button onClick={() => addColumn('col2')}>add-column</button>
}));

vi.mock('components/elements/hit/grid/RecordTable', () => ({
  default: ({ query, items }: any) => <div>{`grid:${query}:${items?.length ?? 0}`}</div>
}));

vi.mock('components/elements/hit/HitCard', () => ({
  default: ({ id }: any) => <div>{`hit:${id}`}</div>
}));

vi.mock('components/elements/view/LayoutToggle', () => ({
  default: () => <div>layout-toggle</div>
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('components/hooks/useMyLocalStorage', () => ({
  useMyLocalStorageItem: () => [25]
}));

vi.mock('components/hooks/useMySnackbar', () => ({
  default: () => ({ showSuccessMessage: mockShowSuccessMessage, showErrorMessage: mockShowErrorMessage })
}));

vi.mock('components/elements/membership/MembershipManagement', () => ({
  MembershipManagement: () => <div>membership</div>
}));

vi.mock('../ErrorBoundary', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

vi.mock('../hits/search/RecordQuery', () => ({
  default: ({ triggerSearch, onChange }: any) => (
    <div>
      <button onClick={() => onChange?.('status:open', false)}>record-query-clean</button>
      <button onClick={() => triggerSearch('status:open')}>record-query-search</button>
    </div>
  )
}));

vi.mock('../hits/search/shared/HitSort', () => ({
  default: () => <div>sort</div>
}));

vi.mock('../hits/search/shared/IndexPicker', () => ({
  default: () => <div>index-picker</div>
}));

vi.mock('../hits/search/shared/SearchSpan', () => ({
  default: () => <div>search-span</div>
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-router', () => ({
  useNavigate: () => mockNavigate,
  useParams: () => routeParamsValue
}));

vi.mock('use-context-selector', () => ({
  useContextSelector: (context: any, selector: any) => {
    if (context === viewContextToken) return selector({ addView: mockAddView, editView: mockEditView, getCurrentViews: mockGetCurrentViews });
    if (context === parameterContextToken) return selector(parameterContextValue);
    if (context === recordContextToken) return selector({ loadRecords: mockLoadRecords });
    if (context === recordSearchContextToken) return selector(recordSearchContextValue);
    return undefined;
  }
}));

vi.mock('utils/constants', () => ({
  DEFAULT_QUERY: '*:*',
  StorageKey: { PAGE_COUNT: 'page-count' }
}));

vi.mock('utils/utils', () => ({
  convertDateToLucene: (value: string) => `converted:${value}`
}));

vi.mock('utils/viewUtils', () => ({
  buildViewUrl: (view: any) => `/views/${view.view_id}`
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === gridColumnsContextToken) return gridColumnsContextValue;
      return actual.useContext(context);
    }
  };
});

import ViewComposer from './ViewComposer';

describe('ViewComposer', () => {
  beforeEach(() => {
    routeParamsValue = {};
    searchResponseValue = {
      total: 2,
      offset: 0,
      rows: 25,
      items: [
        { __index: 'hit', howler: { id: 'hit-1' } },
        { __index: 'event', howler: { id: 'event-1' } }
      ]
    };
    parameterContextValue = {
      indexes: undefined,
      setIndexes: vi.fn((value: any) => { parameterContextValue.indexes = value; }),
      query: '',
      setQuery: vi.fn((value: any) => { parameterContextValue.query = value; }),
      sort: 'created desc',
      setSort: vi.fn((value: any) => { parameterContextValue.sort = value; }),
      span: '24h',
      setSpan: vi.fn((value: any) => { parameterContextValue.span = value; })
    };
    recordSearchContextValue = {
      displayType: 'grid',
      setDisplayType: vi.fn((value: any) => { recordSearchContextValue.displayType = value; })
    };
    const columns = ['col1'];
    gridColumnsContextValue = {
      columns,
      setColumns: vi.fn((value: string[]) => {
        columns.splice(0, columns.length, ...value);
      }),
      columnWidths: { col1: 120 },
      isReady: true
    };
    mockDispatchApi.mockReset();
    mockDispatchApi.mockResolvedValue(searchResponseValue);
    mockShowSuccessMessage.mockReset();
    mockShowErrorMessage.mockReset();
    mockNavigate.mockReset();
    mockAddView.mockReset();
    mockEditView.mockReset();
    mockGetCurrentViews.mockReset();
    mockLoadRecords.mockReset();
  });

  it('runs an initial search, adds a column, and creates a new view', async () => {
    mockAddView.mockResolvedValueOnce({ view_id: 'new-view' });

    render(<ViewComposer />);

    await waitFor(() =>
      expect(mockDispatchApi).toHaveBeenCalledWith(
        {
          indexes: ['hit'],
          body: {
            rows: 25,
            query: '*:*',
            sort: 'created desc',
            filters: ['event.created:converted:24h'],
            metadata: ['template', 'analytic']
          }
        },
        { showError: false, throwError: true }
      )
    );
    expect(mockLoadRecords).toHaveBeenCalledWith(searchResponseValue.items);
    expect(screen.getByText('grid:*:*:2')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('route.views.name'), { target: { value: 'New View' } });
    fireEvent.click(screen.getByText('unchecked'));
    fireEvent.click(screen.getByText('add-column'));
    fireEvent.click(screen.getByText('save'));

    await waitFor(() =>
      expect(mockAddView).toHaveBeenCalledWith({
        title: 'New View',
        type: 'global',
        query: '*:*',
        indexes: ['hit'],
        sort: 'created desc',
        span: '24h',
        settings: {
          advance_on_triage: true,
          display: 'grid',
          columns: [
            { field: 'col1', width: 120 },
            { field: 'col2', width: null }
          ]
        }
      })
    );
    expect(mockNavigate).toHaveBeenCalledWith('/views/new-view');
    expect(mockShowSuccessMessage).toHaveBeenCalledWith('route.views.create.success');
  });

  it('loads an existing view, re-searches with loaded params, and updates it', async () => {
    routeParamsValue = { id: 'view-1' };
    recordSearchContextValue.displayType = 'list';
    mockGetCurrentViews.mockResolvedValueOnce([
      {
        view_id: 'view-1',
        title: 'Existing View',
        type: 'personal',
        query: 'status:open',
        indexes: ['event'],
        sort: 'event.created asc',
        span: '7d',
        settings: { advance_on_triage: true, display: 'list' }
      }
    ]);
    mockEditView.mockResolvedValueOnce(undefined);

    render(<ViewComposer />);

    await waitFor(() => expect(mockGetCurrentViews).toHaveBeenCalledWith({ views: ['view-1'] }));
    await waitFor(() =>
      expect(mockDispatchApi).toHaveBeenCalledWith(
        {
          indexes: ['event'],
          body: {
            rows: 25,
            query: 'status:open',
            sort: 'event.created asc',
            filters: ['event.created:converted:7d'],
            metadata: ['template', 'analytic']
          }
        },
        { showError: false, throwError: true }
      )
    );
    expect(parameterContextValue.setIndexes).toHaveBeenCalledWith(['event']);
    expect(parameterContextValue.setSort).toHaveBeenCalledWith('event.created asc');
    expect(parameterContextValue.setSpan).toHaveBeenCalledWith('7d');
    expect(screen.getByText('event:event-1')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('route.views.name'), { target: { value: 'Updated View' } });
    fireEvent.click(screen.getByText('checked'));
    fireEvent.click(screen.getByText('save'));

    await waitFor(() =>
      expect(mockEditView).toHaveBeenCalledWith('view-1', {
        title: 'Updated View',
        type: 'personal',
        query: 'status:open',
        indexes: ['event'],
        sort: 'event.created asc',
        span: '7d',
        settings: {
          advance_on_triage: false,
          display: 'list',
          columns: undefined
        }
      })
    );
    expect(mockShowSuccessMessage).toHaveBeenCalledWith('route.views.update.success');
  });
});
