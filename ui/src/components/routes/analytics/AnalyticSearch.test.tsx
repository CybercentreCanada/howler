/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const listMethodContextToken = vi.hoisted(() => ({ name: 'list-method-context' }));
const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockNavigate = vi.hoisted(() => vi.fn());
const mockSetSearchParams = vi.hoisted(() => vi.fn());
const mockLoad = vi.hoisted(() => vi.fn());
const mockRequest = vi.hoisted(() => vi.fn());
const mockSetUser = vi.hoisted(() => vi.fn());

let searchParamsValue = new URLSearchParams();
let responseValue: any = {
  total: 1,
  items: [{ analytic_id: 'an-1', name: 'Alpha', owner: 'owner-1', contributors: ['owner-1', 'user-2'], detections: ['d1'] }]
};
let appUserValue: any = {
  user: { username: 'demo', favourite_analytics: [] },
  setUser: mockSetUser
};

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return {
    ...actual,
    Star: () => <div>star</div>,
    StarBorder: () => <div>star-border</div>
  };
});

vi.mock('@mui/material', () => ({
  AvatarGroup: ({ children }: any) => <div>{children}</div>,
  Card: ({ children, onClick }: any) => <div onClick={onClick}>{children}</div>,
  CardContent: ({ children }: any) => <div>{children}</div>,
  CardHeader: ({ title }: any) => <div>{title}</div>,
  Chip: ({ label }: any) => <div>{label}</div>,
  Divider: () => <div>divider</div>,
  Grid: ({ children }: any) => <div>{children}</div>,
  IconButton: ({ children, onClick }: any) => <button onClick={onClick}>{children}</button>,
  Stack: ({ children }: any) => <div>{children}</div>,
  Tooltip: ({ children }: any) => <div>{children}</div>,
  Typography: ({ children }: any) => <div>{children}</div>,
  useTheme: () => ({ palette: { text: { disabled: '#999' } }, spacing: (v: number) => `${v * 8}px` })
}));

vi.mock('@tui/core', () => ({
  useAppUser: () => appUserValue
}));

vi.mock('api', () => ({
  default: {
    analytic: {
      favourite: {
        post: (id: string) => ({ id, op: 'add' }),
        del: (id: string) => ({ id, op: 'remove' })
      }
    },
    search: {
      analytic: {
        post: 'analytic-search'
      }
    }
  }
}));

vi.mock('components/app/providers/SearchResponseProvider', () => ({
  __esModule: true,
  default: ({ children }: any) => <div>{children}</div>,
  createSearchResponseContext: () => ({}),
  useSearchResponseContext: () => ({
    response: responseValue,
    request: mockRequest
  })
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

vi.mock('components/elements/display/HowlerAvatar', () => ({
  default: ({ userId }: any) => <div>{`avatar:${userId}`}</div>
}));

vi.mock('components/elements/display/ItemManager', () => ({
  default: (props: any) => (
    <div>
      <button onClick={() => props.onSearch()}>search</button>
      <button onClick={() => props.onPageChange(50)}>page</button>
      <div>{props.aboveSearch}</div>
      {props.response?.items?.map((item: any) => (
        <div key={item.analytic_id}>{props.renderer({ item: { item } }, () => 'card')}</div>
      ))}
    </div>
  )
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('components/hooks/useMyLocalStorage', () => ({
  useMyLocalStorageItem: () => [25]
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-router', () => ({
  useNavigate: () => mockNavigate,
  useSearchParams: () => [searchParamsValue, mockSetSearchParams]
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === listMethodContextToken) {
        return { load: mockLoad };
      }
      return actual.useContext(context);
    }
  };
});

import AnalyticSearch from './AnalyticSearch';

describe('AnalyticSearch', () => {
  beforeEach(() => {
    searchParamsValue = new URLSearchParams();
    responseValue = {
      total: 1,
      items: [{ analytic_id: 'an-1', name: 'Alpha', owner: 'owner-1', contributors: ['owner-1', 'user-2'], detections: ['d1', 'd2', 'd3', 'd4', 'd5', 'd6'] }]
    };
    appUserValue = {
      user: { username: 'demo', favourite_analytics: [] },
      setUser: mockSetUser
    };
    mockDispatchApi.mockReset().mockImplementation(async value => value);
    mockNavigate.mockReset();
    mockSetSearchParams.mockReset();
    mockLoad.mockReset();
    mockRequest.mockReset().mockResolvedValue(responseValue);
    mockSetUser.mockReset();
  });

  it('searches analytics, paginates, navigates, and toggles favourites', async () => {
    render(<AnalyticSearch />);

    await waitFor(() => expect(mockRequest).toHaveBeenCalledWith('analytic-search', {
      query: 'name:** OR detections:**',
      rows: 25,
      offset: 0
    }));
    expect(mockLoad).toHaveBeenCalledWith([expect.objectContaining({ id: 'an-1' })]);
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.getByText('avatar:owner-1')).toBeInTheDocument();
    expect(screen.getByText('avatar:user-2')).toBeInTheDocument();
    expect(screen.getByText('+ 1')).toBeInTheDocument();

    fireEvent.click(screen.getByText('page'));
    expect(mockSetSearchParams).toHaveBeenCalled();

    fireEvent.click(screen.getByText('star-border'));
    await waitFor(() => expect(mockSetUser).toHaveBeenCalledWith(expect.objectContaining({ favourite_analytics: ['an-1'] })));

    fireEvent.click(screen.getByText('Alpha'));
    expect(mockNavigate).toHaveBeenCalledWith('/analytics/an-1');
  });

  it('removes favourites when the analytic is already pinned', async () => {
    appUserValue = {
      user: { username: 'demo', favourite_analytics: ['an-1'] },
      setUser: mockSetUser
    };

    render(<AnalyticSearch />);
    fireEvent.click(screen.getByText('star'));
    await waitFor(() => expect(mockSetUser).toHaveBeenCalledWith(expect.objectContaining({ favourite_analytics: [] })));
  });
});
