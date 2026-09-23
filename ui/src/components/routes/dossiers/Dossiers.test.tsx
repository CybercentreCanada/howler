/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const modalContextToken = vi.hoisted(() => ({ name: 'modal-context' }));
const listMethodContextToken = vi.hoisted(() => ({ name: 'list-method-context' }));
const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockShowSuccessMessage = vi.hoisted(() => vi.fn());
const mockNavigate = vi.hoisted(() => vi.fn());
const mockSetSearchParams = vi.hoisted(() => vi.fn());
const mockLoad = vi.hoisted(() => vi.fn());
const mockRequest = vi.hoisted(() => vi.fn());
const mockRemove = vi.hoisted(() => vi.fn());
const mockGetSearchRequestData = vi.hoisted(() => vi.fn((data: any) => ({ offset: data.offset })));
const mockDossierDelete = vi.hoisted(() => vi.fn((dossierId: string) => ({ dossierId })));

let searchParamsValue = new URLSearchParams();
let responseValue: any = {
  total: 2,
  items: [
    { dossier_id: 'dos-1', name: 'Alpha' },
    { dossier_id: 'dos-2', name: 'Bravo' }
  ]
};

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return { ...actual, Topic: () => <div>topic-icon</div> };
});

vi.mock('@mui/material', () => ({
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('api', () => ({
  default: {
    search: {
      dossier: {
        post: 'dossier-search'
      }
    },
    dossier: {
      del: mockDossierDelete
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
      <button onClick={() => props.onPageChange(30)}>page</button>
      <button onClick={() => props.onCreate()}>create</button>
      <button onClick={() => props.onSelect({ id: 'dos-1' })}>select</button>
      <div>{props.aboveSearch}</div>
      <div>{String(props.hasError)}</div>
      <div>{String(props.searching)}</div>
      {props.response?.items?.map((item: any) => (
        <div key={item.dossier_id}>{props.renderer({ item: { item } }, () => 'card')}</div>
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

vi.mock('./DossierCard', () => ({
  default: ({ dossier, onDelete, className }: any) => (
    <div>
      <span>{`${dossier.dossier_id}:${className}`}</span>
      <button
        onClick={event =>
          onDelete(
            {
              preventDefault: () => undefined,
              stopPropagation: () => undefined
            } as any,
            dossier.dossier_id
          )
        }
      >
        remove-{dossier.dossier_id}
      </button>
    </div>
  )
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === listMethodContextToken) {
        return { load: mockLoad };
      }
      if (context === modalContextToken) {
        return { withConfirmDeleteModal: (fn: any) => void fn() };
      }
      return actual.useContext(context);
    }
  };
});

import Dossiers from './Dossiers';

describe('Dossiers', () => {
  beforeEach(() => {
    searchParamsValue = new URLSearchParams();
    responseValue = {
      total: 2,
      items: [
        { dossier_id: 'dos-1', name: 'Alpha' },
        { dossier_id: 'dos-2', name: 'Bravo' }
      ]
    };
    mockDispatchApi.mockReset();
    mockShowSuccessMessage.mockReset();
    mockNavigate.mockReset();
    mockSetSearchParams.mockReset();
    mockLoad.mockReset();
    mockRequest.mockReset();
    mockRemove.mockReset();
    mockGetSearchRequestData.mockClear();
    mockDossierDelete.mockReset();
  });

  it('searches, paginates, and navigates dossiers', async () => {
    render(<Dossiers />);

    await waitFor(() => expect(mockRequest).toHaveBeenCalledWith('dossier-search', { query: '*:*', rows: 25, offset: 0 }));
    expect(mockLoad).toHaveBeenCalledWith([
      expect.objectContaining({ id: 'dos-1' }),
      expect.objectContaining({ id: 'dos-2' })
    ]);

    fireEvent.click(screen.getByText('page'));
    expect(mockSetSearchParams).toHaveBeenCalled();

    fireEvent.click(screen.getByText('select'));
    expect(mockNavigate).toHaveBeenCalledWith('/dossiers/dos-1/edit');

    fireEvent.click(screen.getByText('create'));
    expect(mockNavigate).toHaveBeenCalledWith('/dossiers/create');
  });

  it('deletes dossiers and handles delete failures', async () => {
    mockDispatchApi.mockResolvedValueOnce({});
    render(<Dossiers />);

    fireEvent.click(screen.getByText('remove-dos-1'));
    await waitFor(() => expect(mockDossierDelete).toHaveBeenCalledWith('dos-1'));
    expect(mockRemove).toHaveBeenCalledWith('dos-1');
    expect(mockShowSuccessMessage).toHaveBeenCalledWith('route.dossiers.manager.delete.success');

    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    mockDispatchApi.mockRejectedValueOnce(new Error('delete failed'));
    fireEvent.click(screen.getByText('remove-dos-2'));
    await waitFor(() => expect(warnSpy).toHaveBeenCalled());
  });
});
