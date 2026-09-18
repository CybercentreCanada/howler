/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const listMethodContextToken = vi.hoisted(() => ({ name: 'list-method-context' }));
const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockNavigate = vi.hoisted(() => vi.fn());
const mockSetSearchParams = vi.hoisted(() => vi.fn());
const mockLoad = vi.hoisted(() => vi.fn());

let searchParamsValue = new URLSearchParams();
let tableSelect: any;

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return {
    ...actual,
    Close: () => <div>close-icon</div>,
    Search: () => <div>search-icon</div>
  };
});

vi.mock('@mui/material', () => ({
  Box: ({ children }: any) => <div>{children}</div>,
  Chip: ({ label }: any) => <div>{label}</div>,
  Grid: ({ children }: any) => <div>{children}</div>,
  IconButton: ({ children, onClick }: any) => <button onClick={onClick}>{children}</button>,
  LinearProgress: () => <div>loading</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  TextField: ({ value, onChange, onKeyDown, InputProps }: any) => (
    <div>
      {InputProps?.startAdornment}
      <input aria-label="phrase" value={value} onChange={onChange} onKeyDown={onKeyDown} />
      {InputProps?.endAdornment}
    </div>
  ),
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('@tui/core', () => ({
  PageCenter: ({ children }: any) => <div>{children}</div>,
  parseEvent: (event: any) => ({ isEnter: event.key === 'Enter' })
}));

vi.mock('api', () => ({
  default: {
    search: {
      user: {
        post: (body: any) => body
      }
    }
  }
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

vi.mock('components/elements/addons/lists', () => ({
  TuiListProvider: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/elements/addons/lists/table/TuiTable', () => ({
  default: ({ columns, onRowSelect, children }: any) => {
    tableSelect = onRowSelect;
    return (
      <div>
        <div>{children(['group-a', 'group-b'], undefined, { column: 'groups' })}</div>
        <div>{columns.map((column: any) => column.column).join(',')}</div>
      </div>
    );
  }
}));

vi.mock('components/elements/addons/lists/TuiListProvider', () => ({
  TuiListMethodContext: listMethodContextToken
}));

vi.mock('components/elements/addons/search/SearchPagination', () => ({
  default: ({ onChange }: any) => <button onClick={() => onChange(30)}>page</button>
}));

vi.mock('components/elements/addons/search/SearchTotal', () => ({
  default: ({ total }: any) => <div>{`total:${total}`}</div>
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
  Link: ({ children }: any) => <div>{children}</div>,
  useNavigate: () => mockNavigate,
  useSearchParams: () => [searchParamsValue, mockSetSearchParams]
}));

vi.mock('utils/stringUtils', async importOriginal => {
  const actual = await importOriginal<typeof import('utils/stringUtils')>();
  return {
    ...actual,
    sanitizeLuceneQuery: (value: string) => value.replaceAll(':', '\\:')
  };
});

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

import UserSearchProvider from './UserSearch';

describe('UserSearch', () => {
  beforeEach(() => {
    searchParamsValue = new URLSearchParams();
    tableSelect = undefined;
    mockDispatchApi.mockReset().mockResolvedValue({
      total: 1,
      offset: 0,
      rows: 25,
      items: [{ username: 'alice', name: 'Alice', email: 'a@example.com', groups: ['group-a', 'group-b'] }]
    });
    mockNavigate.mockReset();
    mockSetSearchParams.mockReset();
    mockLoad.mockReset();
  });

  it('searches users, sanitizes input, paginates, clears, and navigates selected rows', async () => {
    render(<UserSearchProvider />);

    await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
    expect(mockLoad).toHaveBeenCalledWith([
      {
        id: 'alice',
        item: { username: 'alice', name: 'Alice', email: 'a@example.com', groups: ['group-a', 'group-b'] }
      }
    ]);

    fireEvent.change(screen.getByLabelText('phrase'), { target: { value: 'alice:demo' } });
    fireEvent.keyDown(screen.getByLabelText('phrase'), { key: 'Enter' });
    await waitFor(() =>
      expect(mockDispatchApi.mock.calls.at(-1)[0]).toMatchObject({
        query: 'name:*alice\\:demo* OR uname:*alice\\:demo* OR email:*alice\\:demo*',
        rows: 25,
        offset: 0
      })
    );

    fireEvent.click(screen.getByText('page'));
    expect(mockSetSearchParams).toHaveBeenCalled();

    fireEvent.click(screen.getByText('close-icon').closest('button')!);
    await waitFor(() =>
      expect(mockDispatchApi.mock.calls.at(-1)[0]).toMatchObject({
        query: 'name:*alice\\:demo* OR uname:*alice\\:demo* OR email:*alice\\:demo*'
      })
    );
    expect(screen.getByLabelText('phrase')).toHaveValue('');

    tableSelect({ item: { username: 'alice' } });
    expect(mockNavigate).toHaveBeenCalledWith('alice');
    expect(screen.getByText('group-a')).toBeInTheDocument();
    expect(screen.getByText('total:1')).toBeInTheDocument();
  });
});
