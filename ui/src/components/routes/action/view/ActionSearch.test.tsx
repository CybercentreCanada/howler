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
const mockDeleteAction = vi.hoisted(() => vi.fn());
const modalContextToken = vi.hoisted(() => ({ name: 'modal-context' }));
const listMethodContextToken = vi.hoisted(() => ({ name: 'list-method-context' }));

let searchParamsValue = new URLSearchParams();
let responseValue: any = {
  total: 1,
  items: [
    { action_id: 'action-1', name: 'Action One', owner: 'demo', triggers: ['manual'], operations: [{ operation_id: 'archive' }], query: 'status:open' }
  ]
};
let appUserValue: any = {
  user: { username: 'demo', roles: ['automation_basic'] }
};

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return {
    ...actual,
    Delete: () => <div>delete-icon</div>,
    Engineering: () => <div>engineering-icon</div>,
    Terminal: () => <div>terminal-icon</div>
  };
});

vi.mock('@mui/material', () => ({
  Autocomplete: ({ onChange }: any) => <button onClick={() => onChange?.(null, ['manual'])}>set-trigger</button>,
  Card: ({ children, onClick }: any) => <div onClick={onClick}>{children}</div>,
  CardContent: ({ children }: any) => <div>{children}</div>,
  CardHeader: ({ title, subheader }: any) => <div>{title}{subheader}</div>,
  Chip: ({ label }: any) => <div>{label}</div>,
  Grid: ({ children }: any) => <div>{children}</div>,
  IconButton: ({ children, onClick }: any) => <button onClick={onClick}>{children}</button>,
  Stack: ({ children }: any) => <div>{children}</div>,
  TextField: () => <div>text-field</div>,
  Tooltip: ({ children }: any) => <div>{children}</div>,
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('@tui/core', () => ({
  useAppUser: () => appUserValue
}));

vi.mock('api', () => ({
  default: {
    search: {
      action: {
        post: 'action-search'
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
      <button onClick={() => props.onCreate?.()}>create</button>
      <div>{props.searchFilters}</div>
      {props.response?.items?.map((item: any) => (
        <div key={item.action_id}>{props.renderer({ item: { item } }, () => 'card')}</div>
      ))}
    </div>
  )
}));

vi.mock('components/elements/membership/Members', () => ({
  default: ({ item }: any) => <div>{`members:${item.action_id}`}</div>
}));

vi.mock('components/hooks/useMyLocalStorage', () => ({
  useMyLocalStorageItem: () => [25]
}));

vi.mock('components/hooks/useMySnackbar', () => ({
  default: () => ({ showSuccessMessage: mockShowSuccessMessage })
}));

vi.mock('react-i18next', () => ({
  Trans: ({ values }: any) => <div>{values?.triggers}</div>,
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-router', () => ({
  useNavigate: () => mockNavigate,
  useSearchParams: () => [searchParamsValue, mockSetSearchParams]
}));

vi.mock('../useMyActionFunctions', () => ({
  default: () => ({ deleteAction: mockDeleteAction })
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

import ActionSearch from './ActionSearch';

describe('ActionSearch', () => {
  beforeEach(() => {
    searchParamsValue = new URLSearchParams();
    responseValue = {
      total: 1,
      items: [
        { action_id: 'action-1', name: 'Action One', owner: 'demo', triggers: ['manual'], operations: [{ operation_id: 'archive' }], query: 'status:open' }
      ]
    };
    appUserValue = { user: { username: 'demo', roles: ['automation_basic'] } };
    mockShowSuccessMessage.mockReset();
    mockNavigate.mockReset();
    mockSetSearchParams.mockReset();
    mockLoad.mockReset();
    mockRequest.mockReset();
    mockRemove.mockReset();
    mockGetSearchRequestData.mockClear();
    mockDeleteAction.mockReset();
  });

  it('searches, filters, paginates, and navigates to create/detail pages', async () => {
    render(<ActionSearch />);

    await waitFor(() =>
      expect(mockRequest).toHaveBeenCalledWith('action-search', {
        query: 'name:(**) OR query:(**)',
        rows: 25,
        offset: 0
      })
    );
    expect(mockLoad).toHaveBeenCalledWith([expect.objectContaining({ id: 'action-1' })]);
    expect(screen.getByText('status:open')).toBeInTheDocument();
    expect(screen.getByText('members:action-1')).toBeInTheDocument();
    expect(screen.getByText('operations.archive')).toBeInTheDocument();

    fireEvent.click(screen.getByText('set-trigger'));
    await waitFor(() =>
      expect(mockRequest).toHaveBeenLastCalledWith('action-search', {
        query: '(name:(**) OR query:(**)) AND (triggers:(manual))',
        rows: 25,
        offset: 0
      })
    );

    fireEvent.click(screen.getByText('page'));
    expect(mockSetSearchParams).toHaveBeenCalled();

    fireEvent.click(screen.getByText('create'));
    expect(mockNavigate).toHaveBeenCalledWith('/action/execute');

    fireEvent.click(screen.getByText('Action One'));
    expect(mockNavigate).toHaveBeenCalledWith('/action/action-1');
  });

  it('deletes actions and shows a success message', async () => {
    render(<ActionSearch />);

    fireEvent.click(screen.getByText('delete-icon'));
    await waitFor(() => expect(mockDeleteAction).toHaveBeenCalledWith('action-1'));
    expect(mockRemove).toHaveBeenCalledWith('action-1');
    expect(mockShowSuccessMessage).toHaveBeenCalledWith('route.actions.manager.delete.success');
  });
});
