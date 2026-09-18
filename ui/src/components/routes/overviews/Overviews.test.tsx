/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockShowSuccessMessage = vi.hoisted(() => vi.fn());
const mockNavigate = vi.hoisted(() => vi.fn());
const mockSetSearchParams = vi.hoisted(() => vi.fn());
const mockLoad = vi.hoisted(() => vi.fn());
const mockRequest = vi.hoisted(() => vi.fn());
const mockRemove = vi.hoisted(() => vi.fn());
const mockGetSearchRequestData = vi.hoisted(() => vi.fn((data: any) => ({ offset: data.offset })));
const mockOverviewDelete = vi.hoisted(() => vi.fn((overviewId: string) => ({ overviewId })));
const analyticContextToken = vi.hoisted(() => ({ name: 'analytic-context' }));
const listMethodContextToken = vi.hoisted(() => ({ name: 'list-method-context' }));

let searchParamsValue = new URLSearchParams();
let responseValue: any = {
  total: 2,
  items: [
    { overview_id: 'ov-1', analytic: 'Alpha', detection: 'Match' },
    { overview_id: 'ov-2', analytic: 'Bravo', detection: 'Unknown' }
  ]
};
let analyticContextValue: any = {
  analytics: [{ name: 'Alpha', detections: ['match'] }]
};

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return {
    ...actual,
    Article: () => <div>article-icon</div>
  };
});

vi.mock('@mui/material', () => ({
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('api', () => ({
  default: {
    search: {
      overview: {
        post: 'overview-search'
      }
    },
    overview: {
      del: mockOverviewDelete
    }
  }
}));

vi.mock('components/app/providers/AnalyticProvider', () => ({
  AnalyticContext: analyticContextToken
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
      <button onClick={() => props.onPageChange(50)}>page</button>
      <button onClick={() => props.onCreate()}>create</button>
      <button onClick={() => props.onSelect({ id: 'ov-1', item: responseValue.items[0] })}>select</button>
      <div>{props.aboveSearch}</div>
      <div>{String(props.hasError)}</div>
      <div>{String(props.searching)}</div>
      {props.response?.items?.map((item: any) => (
        <div key={item.overview_id}>{props.renderer({ item: { item, disabled: item.overview_id === 'ov-2' } }, () => 'card')}</div>
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

vi.mock('components/hooks/useMySnackbar', () => ({
  default: () => ({ showSuccessMessage: mockShowSuccessMessage })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-router', () => ({
  useNavigate: () => mockNavigate,
  useSearchParams: () => [searchParamsValue, mockSetSearchParams]
}));

vi.mock('./OverviewCard', () => ({
  default: ({ overview, error, onRemove, className }: any) => (
    <div>
      <span>{`${overview.overview_id}:${String(error)}:${className}`}</span>
      <button onClick={() => onRemove(overview.overview_id)}>remove-{overview.overview_id}</button>
    </div>
  )
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === analyticContextToken) {
        return analyticContextValue;
      }
      if (context === listMethodContextToken) {
        return { load: mockLoad };
      }
      return actual.useContext(context);
    }
  };
});

import Overviews from './Overviews';

describe('Overviews', () => {
  beforeEach(() => {
    searchParamsValue = new URLSearchParams();
    responseValue = {
      total: 2,
      items: [
        { overview_id: 'ov-1', analytic: 'Alpha', detection: 'Match' },
        { overview_id: 'ov-2', analytic: 'Bravo', detection: 'Unknown' }
      ]
    };
    analyticContextValue = { analytics: [{ name: 'Alpha', detections: ['match'] }] };
    mockDispatchApi.mockReset();
    mockShowSuccessMessage.mockReset();
    mockNavigate.mockReset();
    mockSetSearchParams.mockReset();
    mockLoad.mockReset();
    mockRequest.mockReset();
    mockRemove.mockReset();
    mockGetSearchRequestData.mockClear();
    mockOverviewDelete.mockReset();
  });

  it('searches, loads list items, paginates, and navigates', async () => {
    render(<Overviews />);

    await waitFor(() => expect(mockRequest).toHaveBeenCalledWith('overview-search', { query: '*:*', rows: 25, offset: 0 }));
    expect(mockLoad).toHaveBeenCalledWith([
      expect.objectContaining({ id: 'ov-1', disabled: false }),
      expect.objectContaining({ id: 'ov-2', disabled: true })
    ]);

    fireEvent.click(screen.getByText('page'));
    expect(mockSetSearchParams).toHaveBeenCalled();

    fireEvent.click(screen.getByText('select'));
    expect(mockNavigate).toHaveBeenCalledWith('/overviews/view?analytic=Alpha&detection=Match');

    fireEvent.click(screen.getByText('create'));
    expect(mockNavigate).toHaveBeenCalledWith('/overviews/view');
  });

  it('removes overviews and tolerates delete errors', async () => {
    mockDispatchApi.mockResolvedValueOnce({});
    render(<Overviews />);

    fireEvent.click(screen.getByText('remove-ov-1'));
    await waitFor(() => expect(mockOverviewDelete).toHaveBeenCalledWith('ov-1'));
    expect(mockRemove).toHaveBeenCalledWith('ov-1');
    expect(mockShowSuccessMessage).toHaveBeenCalledWith('route.overviews.manager.delete.success');

    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    mockDispatchApi.mockRejectedValueOnce(new Error('delete failed'));
    fireEvent.click(screen.getByText('remove-ov-2'));
    await waitFor(() => expect(warnSpy).toHaveBeenCalled());
  });
});
