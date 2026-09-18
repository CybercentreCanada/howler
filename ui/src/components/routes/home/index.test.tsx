/// <reference types="vitest" />
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockSetDashboard = vi.hoisted(() => vi.fn());
const mockSetRefreshRateBackend = vi.hoisted(() => vi.fn());
const mockSetLastViewed = vi.hoisted(() => vi.fn());
const mockSetUser = vi.hoisted(() => vi.fn());
const mockAddToAppBar = vi.hoisted(() => vi.fn());
const mockRemoveFromAppBar = vi.hoisted(() => vi.fn());
const appBarContextToken = vi.hoisted(() => ({ name: 'app-bar-context' }));

let currentUser: any;
let searchResult = { total: 0 };

vi.mock('@dnd-kit/core', () => ({
  DndContext: ({ children }: any) => <div>{children}</div>,
  KeyboardSensor: function KeyboardSensor() {},
  PointerSensor: function PointerSensor() {},
  closestCenter: {},
  useSensor: vi.fn(() => ({})),
  useSensors: vi.fn(() => [])
}));

vi.mock('@dnd-kit/sortable', () => ({
  SortableContext: ({ children }: any) => <div>{children}</div>,
  arrayMove: (arr: any[], oldIndex: number, newIndex: number) => {
    const next = [...arr];
    const [item] = next.splice(oldIndex, 1);
    next.splice(newIndex, 0, item);
    return next;
  },
  sortableKeyboardCoordinates: vi.fn()
}));

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return {
    ...actual,
    Cancel: () => <div>cancel-icon</div>,
    Check: () => <div>check-icon</div>,
    Close: () => <div>close-icon</div>,
    OpenInNew: () => <div>open-icon</div>
  };
});

vi.mock('@mui/material', () => ({
  Alert: ({ children, action }: any) => <div>{children}{action}</div>,
  AlertTitle: ({ children }: any) => <div>{children}</div>,
  CircularProgress: () => <div>loading</div>,
  Grid: ({ children }: any) => <div>{children}</div>,
  IconButton: ({ children, onClick, component, to }: any) => (
    <button data-component={String(!!component)} data-to={to} onClick={onClick}>
      {children}
    </button>
  ),
  Stack: ({ children }: any) => <div>{children}</div>,
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('@tui/core', () => ({
  PageCenter: ({ children }: any) => <div>{children}</div>,
  useAppUser: () => ({ user: currentUser, setUser: mockSetUser })
}));

vi.mock('api', () => ({
  default: {
    search: {
      hit: {
        post: (payload: any) => payload
      }
    }
  }
}));

vi.mock('branding/AppBrand', () => ({
  AppBrand: () => <div>brand</div>
}));

vi.mock('components/app/providers/AppBarProvider', () => ({
  AppBarContext: appBarContextToken
}));

vi.mock('components/elements/addons/buttons/CustomButton', () => ({
  default: ({ children, onClick, disabled }: any) => <button disabled={disabled} onClick={onClick}>{children}</button>
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('components/hooks/useMyLocalStorage', () => ({
  useMyLocalStorageItem: () => ['2024-01-01T00:00:00', mockSetLastViewed]
}));

vi.mock('components/hooks/useMyUserFunctions', () => ({
  default: () => ({
    setDashboard: mockSetDashboard,
    setRefreshRate: mockSetRefreshRateBackend
  })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: any) => (opts?.count ? `${key}:${opts.count}` : key)
  })
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === appBarContextToken) {
        return { addToAppBar: mockAddToAppBar, removeFromAppBar: mockRemoveFromAppBar };
      }
      return actual.useContext(context);
    }
  };
});

vi.mock('react-router', () => ({
  Link: ({ children, to }: any) => <a href={to}>{children}</a>
}));

vi.mock('../ErrorBoundary', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

vi.mock('./AddNewCard', () => ({
  default: ({ addCard }: any) => (
    <button
      onClick={() =>
        addCard({
          entry_id: 'new-entry',
          type: 'view',
          config: JSON.stringify({ viewId: 'new-view' })
        })
      }
    >
      add-card
    </button>
  )
}));

vi.mock('./AnalyticCard', () => ({
  default: ({ analyticId, type }: any) => <div>{`analytic:${analyticId}:${type}`}</div>
}));

vi.mock('./EntryWrapper', () => ({
  default: ({ children, onDelete, id, editing }: any) => (
    <div>
      <span>{`entry:${id}:${String(editing)}`}</span>
      <button onClick={onDelete}>delete-entry</button>
      {children}
    </div>
  )
}));

vi.mock('./HomeSettings', () => ({
  default: () => null
}));

vi.mock('./ViewCard', () => ({
  default: ({ viewId }: any) => <div>{`view:${viewId}`}</div>
}));

vi.mock('./ViewRefresh', () => ({
  default: () => null
}));

import Home from './index';

describe('Home', () => {
  beforeEach(() => {
    currentUser = {
      username: 'alice',
      dashboard: [],
      refresh_rate: 15
    };
    searchResult = { total: 0 };
    mockDispatchApi.mockReset();
    mockDispatchApi.mockImplementation(async () => searchResult);
    mockSetDashboard.mockReset().mockResolvedValue(undefined);
    mockSetRefreshRateBackend.mockReset().mockResolvedValue(undefined);
    mockSetLastViewed.mockReset();
    mockSetUser.mockReset();
    mockAddToAppBar.mockReset();
    mockRemoveFromAppBar.mockReset();
  });

  it('renders the empty state and updated-hit alert actions', async () => {
    searchResult = { total: 2 };
    render(
      <Home />
    );

    await waitFor(() => expect(screen.getByText('route.home.alert.updated.description:2')).toBeInTheDocument());
    expect(screen.getByText('route.home.title')).toBeInTheDocument();
    expect(screen.getByText('route.home.description')).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button')[1]);
    expect(mockSetLastViewed).toHaveBeenCalled();
    await waitFor(() => expect(screen.queryByText('route.home.alert.updated.description:2')).not.toBeInTheDocument());
  });

  it('registers app bar actions, debounces refresh-rate saves, and saves dashboard edits', async () => {
    currentUser = {
      username: 'alice',
      refresh_rate: 15,
      dashboard: [
        { entry_id: 'view-entry', type: 'view', config: JSON.stringify({ viewId: 'view-1' }) },
        { entry_id: 'analytic-entry', type: 'analytic', config: JSON.stringify({ analyticId: 'a1', type: 'created' }) }
      ]
    };

    render(
      <Home />
    );

    await waitFor(() => expect(screen.getByText('view:view-1')).toBeInTheDocument());
    expect(screen.getByText('analytic:a1:created')).toBeInTheDocument();
    expect(mockAddToAppBar).toHaveBeenCalledWith('left', 'view_refresh', expect.anything());
    expect(mockAddToAppBar).toHaveBeenCalledWith('left', 'home_settings', expect.anything());

    const homeSettings = mockAddToAppBar.mock.calls.find(([, key]) => key === 'home_settings')![2];

    await act(async () => {
      homeSettings.props.onEdit();
    });
    expect(screen.getByText('cancel')).toBeInTheDocument();

    await act(async () => {
      homeSettings.props.onRefreshRateChange(30);
      await new Promise(resolve => setTimeout(resolve, 550));
    });
    expect(mockSetRefreshRateBackend).toHaveBeenCalledWith(30);

    fireEvent.click(screen.getByText('add-card'));
    const saveButton = screen.getByText('save');
    expect(saveButton).not.toBeDisabled();
    fireEvent.click(saveButton);

    await waitFor(() => expect(mockSetDashboard).toHaveBeenCalled());
    expect(mockSetUser).toHaveBeenCalled();
  });
});
