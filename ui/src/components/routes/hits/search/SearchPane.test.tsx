/// <reference types="vitest" />
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockSetOffset = vi.hoisted(() => vi.fn());
const mockTriggerSearch = vi.hoisted(() => vi.fn());
const mockOnClick = vi.hoisted(() => vi.fn());

const parameterContextToken = vi.hoisted(() => ({ name: 'parameter-context' }));
const recordContextToken = vi.hoisted(() => ({ name: 'record-context' }));
const searchContextToken = vi.hoisted(() => ({ name: 'search-context' }));

let contextValues: Record<string, any>;

vi.mock('@mui/icons-material', () => ({
  ErrorOutline: () => <div>error-icon</div>
}));

vi.mock('@mui/material', () => ({
  Alert: ({ children }: any) => <div>{children}</div>,
  AlertTitle: ({ children }: any) => <div>{children}</div>,
  Box: ({ children, id, onAuxClick, onClick, flex }: any) => (
    <div id={id} data-flex={flex} onAuxClick={onAuxClick} onClick={onClick}>
      {children}
    </div>
  ),
  LinearProgress: () => <div>loading-bar</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  Tooltip: ({ children }: any) => <>{children}</>,
  Typography: ({ children }: any) => <div>{children}</div>,
  useMediaQuery: () => false,
  useTheme: () => ({
    transitions: { create: () => 'transition' },
    palette: { primary: { main: '#00f' }, text: { secondary: '#666' } },
    shape: { borderRadius: 4 }
  })
}));

vi.mock('@mui/material/colors', () => ({
  grey: { 500: '#999' }
}));

vi.mock('@tui/core', () => ({
  AppListEmpty: () => <div>empty-list</div>,
  PageCenter: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/app/providers/ParameterProvider', () => ({
  ParameterContext: parameterContextToken
}));

vi.mock('components/app/providers/RecordProvider', () => ({
  RecordContext: recordContextToken
}));

vi.mock('components/app/providers/RecordSearchProvider', () => ({
  RecordSearchContext: searchContextToken
}));

vi.mock('components/elements/addons/layout/FlexOne', () => ({
  default: () => <div>flex-one</div>
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

vi.mock('components/elements/addons/search/SearchPagination', () => ({
  default: ({ onChange }: any) => <button onClick={() => onChange(50)}>paginate</button>
}));

vi.mock('components/elements/addons/search/SearchTotal', () => ({
  default: ({ total, pageLength, offset }: any) => <div>{`total:${total}:${pageLength}:${offset}`}</div>
}));

vi.mock('components/elements/display/HowlerCard', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/elements/event/EventCard', () => ({
  default: ({ id }: any) => <div>{`event-card:${id}`}</div>
}));

vi.mock('components/elements/hit/HitCard', () => ({
  default: ({ id, layout }: any) => <div>{`hit-card:${id}:${layout}`}</div>
}));

vi.mock('components/elements/hit/HitLayout', () => ({
  HitLayout: { NORMAL: 'normal', COMFY: 'comfy' }
}));

vi.mock('components/elements/record/RecordContextMenu', () => ({
  default: ({ children, getSelectedId }: any) => (
    <div data-selected={getSelectedId({ target: { closest: () => ({ id: 'selected-id' }) } })}>{children}</div>
  )
}));

vi.mock('components/hooks/useMyLocalStorage', () => ({
  useMyLocalStorageItem: (key: string) => {
    if (key === 'SEARCH_PANE_WIDTH') return [1200];
    if (key === 'PAGE_COUNT') return [25];
    if (key === 'HIT_LAYOUT') return ['normal'];
    return [null];
  }
}));

vi.mock('components/hooks/useRecordSelection', () => ({
  default: () => ({ onClick: mockOnClick })
}));

vi.mock('react-device-detect', () => ({
  isMobile: false
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('use-context-selector', () => ({
  useContextSelector: (context: any, selector: any) => {
    if (context === parameterContextToken) return selector(contextValues.parameter);
    if (context === recordContextToken) return selector(contextValues.record);
    if (context === searchContextToken) return selector(contextValues.search);
    return undefined;
  }
}));

vi.mock('utils/constants', () => ({
  StorageKey: { SEARCH_PANE_WIDTH: 'SEARCH_PANE_WIDTH', PAGE_COUNT: 'PAGE_COUNT', HIT_LAYOUT: 'HIT_LAYOUT' }
}));

vi.mock('utils/typeUtils', () => ({
  isEvent: (record: any) => record?.__index === 'event',
  isHit: (record: any) => record?.__index === 'hit'
}));

vi.mock('./QuerySettings', () => ({
  default: ({ verticalSorters }: any) => <div>{`query-settings:${String(verticalSorters)}`}</div>
}));

vi.mock('./RecordQuery', () => ({
  default: ({ searching, triggerSearch }: any) => (
    <button onClick={() => triggerSearch('query')} disabled={searching}>
      record-query
    </button>
  )
}));

vi.mock('./shared/SearchActionMenu', () => ({
  default: ({ query }: any) => <div>{`search-actions:${query}`}</div>
}));

import SearchPane from './SearchPane';

describe('SearchPane', () => {
  beforeEach(() => {
    mockSetOffset.mockReset();
    mockTriggerSearch.mockReset();
    mockOnClick.mockReset();
    contextValues = {
      parameter: { query: 'status:open', setOffset: mockSetOffset, selected: 'hit-1' },
      record: { selectedRecords: [{ howler: { id: 'event-1' } }] },
      search: { search: mockTriggerSearch, searching: false, response: undefined, error: '' }
    };
    vi.stubGlobal('open', vi.fn());
  });

  it('shows the empty state and can trigger a search', () => {
    render(<SearchPane />);

    expect(screen.getByText('empty-list')).toBeInTheDocument();
    expect(screen.getByText('search-actions:status:open')).toBeInTheDocument();
    fireEvent.click(screen.getByText('record-query'));
    expect(mockTriggerSearch).toHaveBeenCalledWith('query');
  });

  it('renders search results, errors, pagination, and supports selection interactions', () => {
    contextValues.search = {
      search: mockTriggerSearch,
      searching: true,
      error: 'boom',
      response: {
        total: 3,
        offset: 25,
        items: [
          { __index: 'hit', howler: { id: 'hit-1' } },
          { __index: 'event', howler: { id: 'event-1' } },
          { __index: 'other', howler: { id: 'bad-1' } }
        ]
      }
    };

    render(<SearchPane />);

    expect(screen.getByText('error-icon')).toBeInTheDocument();
    expect(screen.getByText('loading-bar')).toBeInTheDocument();
    expect(screen.getByText('total:3:3:25')).toBeInTheDocument();
    expect(screen.getByText('hit-card:hit-1:normal')).toBeInTheDocument();
    expect(screen.getByText('event-card:event-1')).toBeInTheDocument();
    expect(screen.getByText('hit.search.record.invalid')).toBeInTheDocument();

    fireEvent.click(screen.getByText('paginate'));
    expect(mockSetOffset).toHaveBeenCalledWith(50);

    fireEvent.click(screen.getByText('hit-card:hit-1:normal').parentElement!);
    expect(mockOnClick).toHaveBeenCalled();

    fireEvent(
      screen.getByText('hit-card:hit-1:normal').parentElement!,
      new MouseEvent('auxclick', { bubbles: true, button: 1 })
    );
    expect(window.open).toHaveBeenCalledWith(`${window.origin}/hits/hit-1`, '_blank');
  });
});
