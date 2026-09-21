/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockFetchViews = vi.hoisted(() => vi.fn());
const mockSetSelected = vi.hoisted(() => vi.fn());
const mockSetQuery = vi.hoisted(() => vi.fn());
const mockSetOffset = vi.hoisted(() => vi.fn());
const mockAddRecordToSelection = vi.hoisted(() => vi.fn());
const mockRemoveRecordFromSelection = vi.hoisted(() => vi.fn());
const mockClearSelectedRecords = vi.hoisted(() => vi.fn());

const parameterContextToken = vi.hoisted(() => ({ name: 'parameter-context' }));
const recordContextToken = vi.hoisted(() => ({ name: 'record-context' }));
const recordSearchContextToken = vi.hoisted(() => ({ name: 'record-search-context' }));
const viewContextToken = vi.hoisted(() => ({ name: 'view-context' }));

let parameterContextValue: any;
let recordContextValue: any;
let recordSearchContextValue: any;
let locationValue = { pathname: '/hits', search: '' };
let routeParamsValue: any = {};
let forceDrawerValue = false;
let searchPaneWidthValue: any = null;
let downValue = false;

vi.mock('@mui/icons-material', () => ({
  ChevronLeft: () => <div>chevron-left</div>,
  Close: () => <div>close-icon</div>,
  ManageSearch: () => <div>manage-search</div>
}));

vi.mock('@mui/material', () => ({
  Box: ({ children, onClick }: any) => <div onClick={onClick}>{children}</div>,
  Card: ({ children }: any) => <div>{children}</div>,
  Checkbox: ({ checked, onChange }: any) => <button onClick={() => onChange?.(null, !checked)}>{checked ? 'checked' : 'unchecked'}</button>,
  Collapse: ({ children, in: open }: any) => open ? <div>{children}</div> : null,
  Drawer: ({ children, open }: any) => open ? <div>{children}</div> : null,
  Fab: ({ children, onClick }: any) => <button onClick={onClick}>{children}</button>,
  IconButton: ({ children, onClick }: any) => <button onClick={onClick}>{children}</button>,
  Stack: ({ children }: any) => <div>{children}</div>,
  Tooltip: ({ children }: any) => <>{children}</>,
  Typography: ({ children }: any) => <div>{children}</div>,
  useMediaQuery: () => downValue,
  useTheme: () => ({
    breakpoints: { down: () => '@down' },
    palette: { background: { paper: '#fff' } },
    spacing: (n: number) => `${n}px`,
    transitions: { create: () => 'transition' }
  })
}));

vi.mock('components/app/providers/GridColumnsProvider', () => ({
  __esModule: true,
  default: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/app/providers/ParameterProvider', () => ({
  __esModule: true,
  default: ({ children }: any) => <div>{children}</div>,
  ParameterContext: parameterContextToken
}));

vi.mock('components/app/providers/RecordProvider', () => ({
  RecordContext: recordContextToken
}));

vi.mock('components/app/providers/RecordSearchProvider', () => ({
  __esModule: true,
  default: ({ children }: any) => <div>{children}</div>,
  RecordSearchContext: recordSearchContextToken
}));

vi.mock('components/app/providers/ViewProvider', () => ({
  ViewContext: viewContextToken
}));

vi.mock('components/elements/addons/layout/FlexOne', () => ({
  default: () => <div>flex</div>
}));

vi.mock('components/elements/addons/layout/FlexPort', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/elements/hit/HitSummary', () => ({
  default: ({ response }: any) => <div>{`summary:${response?.items?.length ?? 0}`}</div>
}));

vi.mock('components/hooks/useMyLocalStorage', () => ({
  useMyLocalStorageItem: (key: string) => [
    key === 'SEARCH_PANE_WIDTH' ? searchPaneWidthValue : key === 'FORCE_DRAWER' ? forceDrawerValue : null
  ]
}));

vi.mock('components/routes/ErrorBoundary', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

vi.mock('./InformationPane', () => ({
  default: ({ onClose }: any) => <button onClick={onClose}>information-close</button>
}));

vi.mock('./SearchPane', () => ({
  default: () => <div>search-pane</div>
}));

vi.mock('./grid/RecordGrid', () => ({
  default: () => <div>record-grid</div>
}));

vi.mock('lodash-es', () => ({
  isNull: (value: any) => value === null
}));

vi.mock('react-i18next', () => ({
  Trans: ({ i18nKey, values }: any) => <>{`${i18nKey}:${values?.size ?? ''}`}</>,
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-router', () => ({
  useLocation: () => locationValue,
  useParams: () => routeParamsValue
}));

vi.mock('use-context-selector', () => ({
  useContextSelector: (context: any, selector: any) => {
    if (context === viewContextToken) return selector({ fetchViews: mockFetchViews });
    if (context === parameterContextToken) return selector(parameterContextValue);
    if (context === recordContextToken) return selector(recordContextValue);
    if (context === recordSearchContextToken) return selector(recordSearchContextValue);
    return undefined;
  }
}));

vi.mock('utils/constants', () => ({
  StorageKey: {
    SEARCH_PANE_WIDTH: 'SEARCH_PANE_WIDTH',
    FORCE_DRAWER: 'FORCE_DRAWER'
  }
}));

import RecordBrowser from './RecordBrowser';

describe('RecordBrowser', () => {
  beforeEach(() => {
    parameterContextValue = {
      selected: 'hit-1',
      setSelected: mockSetSelected,
      setQuery: mockSetQuery,
      setOffset: mockSetOffset,
      views: ['view-1']
    };
    recordContextValue = {
      selectedRecords: [{ howler: { id: 'hit-1' } }, { howler: { id: 'hit-2' } }],
      addRecordToSelection: mockAddRecordToSelection,
      removeRecordFromSelection: mockRemoveRecordFromSelection,
      clearSelectedRecords: mockClearSelectedRecords
    };
    recordSearchContextValue = {
      displayType: 'list',
      response: {
        items: [{ howler: { id: 'hit-1' } }, { howler: { id: 'hit-2' } }]
      }
    };
    locationValue = { pathname: '/hits', search: '?q=1' };
    routeParamsValue = {};
    forceDrawerValue = false;
    searchPaneWidthValue = null;
    downValue = false;
    mockFetchViews.mockReset();
    mockSetSelected.mockReset();
    mockSetQuery.mockReset();
    mockSetOffset.mockReset();
    mockAddRecordToSelection.mockReset();
    mockRemoveRecordFromSelection.mockReset();
    mockClearSelectedRecords.mockReset();
  });

  it('shows list search results, manages multi-selection, and closes the side panel', async () => {
    render(<RecordBrowser />);

    await waitFor(() => expect(mockFetchViews).toHaveBeenCalledWith(['view-1']));
    expect(screen.getByText('search-pane')).toBeInTheDocument();
    expect(screen.getByText('summary:2')).toBeInTheDocument();
    expect(screen.getByText('hit.search.selected:2')).toBeInTheDocument();

    fireEvent.click(screen.getByText('checked'));
    expect(mockClearSelectedRecords).toHaveBeenCalled();

    fireEvent.click(screen.getByText('close-icon'));
    expect(mockSetSelected).toHaveBeenCalledWith(null);

    fireEvent.click(screen.getByText('manage-search'));
    expect(mockSetOffset).toHaveBeenCalledWith(0);
    expect(mockSetQuery).toHaveBeenCalledWith('howler.id:(hit-1 OR hit-2)');

    fireEvent.click(screen.getByText('information-close'));
    expect(mockSetSelected).toHaveBeenCalledWith(null);
  });

  it('drops invalid selections and uses the drawer/grid layout when required', async () => {
    parameterContextValue.selected = 'hit-3';
    recordContextValue.selectedRecords = [{ howler: { id: 'hit-3' } }];
    recordSearchContextValue.displayType = 'grid';
    recordSearchContextValue.response = {
      items: [{ howler: { id: 'hit-1' } }]
    };
    downValue = true;

    render(<RecordBrowser />);

    await waitFor(() => expect(mockSetSelected).toHaveBeenCalledWith(null));
    expect(mockRemoveRecordFromSelection).toHaveBeenCalledWith('hit-3');
    expect(screen.getByText('record-grid')).toBeInTheDocument();
    expect(screen.getByText('chevron-left')).toBeInTheDocument();
  });
});
