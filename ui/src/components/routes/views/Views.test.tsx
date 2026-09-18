/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockShowSuccessMessage = vi.hoisted(() => vi.fn());
const mockNavigate = vi.hoisted(() => vi.fn());
const mockSetSearchParams = vi.hoisted(() => vi.fn());
const mockLoad = vi.hoisted(() => vi.fn());
const mockRequest = vi.hoisted(() => vi.fn());
const mockRemove = vi.hoisted(() => vi.fn());
const mockGetSearchRequestData = vi.hoisted(() => vi.fn((data: any) => ({ offset: data.offset })));
const mockAddFavourite = vi.hoisted(() => vi.fn());
const mockRemoveFavourite = vi.hoisted(() => vi.fn());
const mockRemoveView = vi.hoisted(() => vi.fn());
const mockFetchViews = vi.hoisted(() => vi.fn(async () => undefined));
const mockSetDefaultView = vi.hoisted(() => vi.fn());
const modalContextToken = vi.hoisted(() => ({ name: 'modal-context' }));
const viewContextToken = vi.hoisted(() => ({ name: 'view-context' }));
const listMethodContextToken = vi.hoisted(() => ({ name: 'list-method-context' }));

let searchParamsValue = new URLSearchParams();
let responseValue: any = {
  total: 2,
  items: [
    { view_id: 'view-1', title: 'Alpha', query: 'status:open', type: 'global', owner: 'demo', admins: [], members: [] },
    { view_id: 'view-2', title: 'Bravo', query: 'status:closed', type: 'personal', owner: 'other', admins: ['demo'], members: [] }
  ]
};
let appUserValue: any = {
  user: { username: 'demo', favourite_views: ['view-1'], is_admin: false }
};
let viewContextValue: any = {
  fetchViews: mockFetchViews,
  addFavourite: mockAddFavourite,
  removeFavourite: mockRemoveFavourite,
  removeView: mockRemoveView,
  views: {
    'view-1': { view_id: 'view-1', title: 'Alpha', query: 'status:open' },
    'view-2': { view_id: 'view-2', title: 'Bravo', query: 'status:closed' }
  },
  defaultView: 'view-1',
  setDefaultView: mockSetDefaultView
};

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return {
    ...actual,
    Clear: () => <div>clear-icon</div>,
    Edit: () => <div>edit-icon</div>,
    SavedSearch: () => <div>saved-search-icon</div>,
    Star: () => <div>star</div>,
    StarBorder: () => <div>star-border</div>
  };
});

vi.mock('@mui/material', () => ({
  Autocomplete: ({ onOpen, onChange }: any) => (
    <div>
      <button onClick={() => onOpen?.()}>open-default</button>
      <button onClick={() => onChange?.(null, { view_id: 'view-2' })}>change-default</button>
    </div>
  ),
  Card: ({ children }: any) => <div>{children}</div>,
  Checkbox: ({ onChange }: any) => <button onClick={() => onChange?.(null, true)}>toggle-favourites</button>,
  IconButton: ({ children, onClick }: any) => <button onClick={onClick}>{children}</button>,
  Skeleton: () => <div>loading</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  TextField: () => <div>text-field</div>,
  ToggleButton: ({ children }: any) => <button>{children}</button>,
  ToggleButtonGroup: ({ children, onChange }: any) => (
    <div>
      <button onClick={() => onChange?.(null, 'personal')}>filter-personal</button>
      <button onClick={() => onChange?.(null, undefined)}>filter-none</button>
      {children}
    </div>
  ),
  Tooltip: ({ children }: any) => <div>{children}</div>,
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('@tui/core', () => ({
  useAppUser: () => appUserValue
}));

vi.mock('api', () => ({
  default: {
    search: {
      view: {
        post: 'view-search'
      }
    }
  }
}));

vi.mock('components/app/providers/ModalProvider', () => ({
  ModalContext: modalContextToken
}));

vi.mock('components/app/providers/SearchResponseProvider', () => ({
  __esModule: true,
  default: ({ children }: any) => <div>{children}</div>,
  createSearchResponseContext: () => ({}),
  useSearchResponseContext: () => ({
    response: responseValue,
    request: mockRequest,
    remove: mockRemove,
    getSearchRequestData: mockGetSearchRequestData
  })
}));

vi.mock('components/app/providers/ViewProvider', () => ({
  ViewContext: viewContextToken
}));

vi.mock('components/elements/addons/layout/FlexOne', () => ({
  default: () => <div>flex</div>
}));

vi.mock('components/elements/addons/lists', () => ({
  TuiListProvider: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/elements/addons/lists/TuiListProvider', () => ({
  TuiListMethodContext: listMethodContextToken
}));

vi.mock('components/elements/display/ItemManager', () => ({
  default: (props: any) => (
    <div>
      <button onClick={() => props.onSearch()}>search</button>
      <button onClick={() => props.onPageChange(25)}>page</button>
      <button onClick={() => props.onCreate()}>create</button>
      <div>{props.searchFilters}</div>
      <div>{props.afterSearch}</div>
      <div>{props.belowSearch}</div>
      {props.response?.items?.map((item: any) => (
        <div key={item.view_id}>{props.renderer({ item: { item } }, () => 'card')}</div>
      ))}
    </div>
  )
}));

vi.mock('components/elements/membership/Members', () => ({
  default: ({ item }: any) => <div>{`members:${item.view_id}`}</div>
}));

vi.mock('components/elements/view/ViewTitle', () => ({
  ViewTitle: ({ title }: any) => <div>{title}</div>
}));

vi.mock('components/hooks/useMyLocalStorage', () => ({
  useMyLocalStorageItem: () => [25]
}));

vi.mock('components/hooks/useMySnackbar', () => ({
  default: () => ({ showSuccessMessage: mockShowSuccessMessage })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-router', () => ({
  Link: ({ children }: any) => <div>{children}</div>,
  useNavigate: () => mockNavigate,
  useSearchParams: () => [searchParamsValue, mockSetSearchParams]
}));

vi.mock('use-context-selector', () => ({
  useContextSelector: (_context: any, selector: any) => selector(viewContextValue)
}));

vi.mock('utils/viewUtils', () => ({
  buildViewUrl: (view: any) => `/views/${view.view_id}`
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === modalContextToken) {
        return { withConfirmDeleteModal: async (fn: () => Promise<void>) => fn() };
      }
      if (context === listMethodContextToken) {
        return { load: mockLoad };
      }
      return actual.useContext(context);
    }
  };
});

import Views from './Views';

describe('Views', () => {
  beforeEach(() => {
    searchParamsValue = new URLSearchParams();
    responseValue = {
      total: 2,
      items: [
        { view_id: 'view-1', title: 'Alpha', query: 'status:open', type: 'global', owner: 'demo', admins: [], members: [] },
        { view_id: 'view-2', title: 'Bravo', query: 'status:closed', type: 'personal', owner: 'other', admins: ['demo'], members: [] }
      ]
    };
    appUserValue = { user: { username: 'demo', favourite_views: ['view-1'], is_admin: false } };
    viewContextValue = {
      fetchViews: mockFetchViews,
      addFavourite: mockAddFavourite,
      removeFavourite: mockRemoveFavourite,
      removeView: mockRemoveView,
      views: {
        'view-1': { view_id: 'view-1', title: 'Alpha', query: 'status:open' },
        'view-2': { view_id: 'view-2', title: 'Bravo', query: 'status:closed' }
      },
      defaultView: 'view-1',
      setDefaultView: mockSetDefaultView
    };
    mockShowSuccessMessage.mockReset();
    mockNavigate.mockReset();
    mockSetSearchParams.mockReset();
    mockLoad.mockReset();
    mockRequest.mockReset();
    mockRemove.mockReset();
    mockGetSearchRequestData.mockClear();
    mockAddFavourite.mockReset();
    mockRemoveFavourite.mockReset();
    mockRemoveView.mockReset();
    mockFetchViews.mockClear();
    mockSetDefaultView.mockReset();
  });

  it('searches, paginates, filters, and manages favourites/default view', async () => {
    render(<Views />);

    await waitFor(() =>
      expect(mockRequest).toHaveBeenCalledWith('view-search', {
        query: '(title:* OR query:* OR sort:* OR type:* OR owner:*) AND (type:global OR owner:(demo OR none) OR admins:demo OR members:demo) AND type:(*)',
        rows: 25,
        offset: 0
      })
    );
    expect(mockLoad).toHaveBeenCalledWith([
      expect.objectContaining({ id: 'view-1' }),
      expect.objectContaining({ id: 'view-2' })
    ]);

    fireEvent.click(screen.getByText('filter-personal'));
    await waitFor(() =>
      expect(mockRequest).toHaveBeenLastCalledWith('view-search', expect.objectContaining({
        query: expect.stringContaining('type:(personal OR readonly)')
      }))
    );

    fireEvent.click(screen.getByText('page'));
    expect(mockSetSearchParams).toHaveBeenCalled();

    fireEvent.click(screen.getByText('filter-none'));
    expect(screen.getByText('route.views.manager.favourites')).toBeInTheDocument();

    fireEvent.click(screen.getByText('open-default'));
    await waitFor(() => expect(mockFetchViews).toHaveBeenCalled());

    fireEvent.click(screen.getByText('change-default'));
    expect(mockSetDefaultView).toHaveBeenCalledWith('view-2');

    fireEvent.click(screen.getByText('star'));
    await waitFor(() => expect(mockRemoveFavourite).toHaveBeenCalledWith('view-1'));

    fireEvent.click(screen.getByText('star-border'));
    await waitFor(() => expect(mockAddFavourite).toHaveBeenCalledWith('view-2'));
  });

  it('creates, deletes, and shows success feedback', async () => {
    render(<Views />);

    fireEvent.click(screen.getByText('create'));
    expect(mockNavigate).toHaveBeenCalledWith('/views/create');

    fireEvent.click(screen.getAllByText('clear-icon')[0]);
    await waitFor(() => expect(mockRemoveView).toHaveBeenCalledWith('view-1'));
    expect(mockRemove).toHaveBeenCalledWith('view-1');
    expect(mockShowSuccessMessage).toHaveBeenCalledWith('route.views.manager.delete.success');
  });
});
