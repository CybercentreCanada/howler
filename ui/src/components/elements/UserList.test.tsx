import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { UserListContext } from 'components/app/providers/UserListProvider';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key
  })
}));

vi.mock('components/elements/display/HowlerAvatar', () => ({
  default: ({ userId }: { userId?: string | null }) => <div id={`avatar-${userId ?? 'none'}`}>{userId ?? 'none'}</div>
}));

import UserList from './UserList';

const mockFetchUsers = vi.fn();

const defaultUsers: Record<string, any> = {
  analystA: {
    username: 'analystA',
    name: 'Alice Analyst',
    email: 'alice@example.com'
  },
  analystB: {
    username: 'analystB',
    name: 'Bob Analyst',
    email: 'bob@example.com'
  },
  analystC: {
    username: 'analystC',
    name: 'Chris Analyst',
    email: 'chris@example.com'
  }
};

const createWrapper = (users: Record<string, any>) => {
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <UserListContext.Provider
      value={{
        users,
        fetchUsers: mockFetchUsers,
        searchUsers: vi.fn()
      }}
    >
      {children}
    </UserListContext.Provider>
  );

  return Wrapper;
};

describe('UserList', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches users on mount and whenever userIds change', async () => {
    const onChange = vi.fn();
    const { rerender } = render(<UserList i18nLabel="user.list.label" userIds={['analystA']} onChange={onChange} />, {
      wrapper: createWrapper(defaultUsers)
    });

    await waitFor(() => {
      expect(mockFetchUsers).toHaveBeenCalledWith(new Set(['analystA']));
    });

    rerender(<UserList i18nLabel="user.list.label" userIds={['analystA', 'analystB']} onChange={onChange} />);

    await waitFor(() => {
      expect(mockFetchUsers).toHaveBeenCalledWith(new Set(['analystA', 'analystB']));
    });
  });

  it('opens the popover and selects a user in single mode', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(<UserList i18nLabel="user.list.label" userIds={['analystA']} onChange={onChange} />, {
      wrapper: createWrapper(defaultUsers)
    });

    const avatarButton = screen.getByRole('button');
    await user.click(avatarButton);

    const combo = await screen.findByRole('combobox', { name: 'user.list.label' });
    await user.click(combo);

    const listbox = await screen.findByRole('listbox');
    await user.click(within(listbox).getByText('Bob Analyst'));

    expect(onChange).toHaveBeenCalledWith(['analystB']);
  });

  it('renders deduplicated avatars and appends selection in multiple mode', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(<UserList i18nLabel="user.list.label" userIds={['analystA', 'analystA']} onChange={onChange} multiple />, {
      wrapper: createWrapper(defaultUsers)
    });

    expect(screen.getAllByText('analystA')).toHaveLength(1);

    const addButton = screen.getByRole('button');
    await user.click(addButton);

    const combo = await screen.findByRole('combobox', { name: 'user.list.label' });
    await user.click(combo);

    const listbox = await screen.findByRole('listbox');
    await user.click(within(listbox).getByText('Bob Analyst'));

    expect(onChange).toHaveBeenCalledWith(expect.arrayContaining(['analystA', 'analystB']));
  });

  it('does not open popover when disabled', async () => {
    const onChange = vi.fn();

    render(
      <UserList
        i18nLabel="user.list.label"
        userIds={['analystA']}
        onChange={onChange}
        disabled
        multiple
        variant="list"
      />,
      {
        wrapper: createWrapper(defaultUsers)
      }
    );

    const button = screen.getByRole('button');
    expect(button).toBeDisabled();

    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
  });

  it('emits an empty list when single-select value is cleared', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(<UserList i18nLabel="user.list.label" userIds={['analystA']} onChange={onChange} />, {
      wrapper: createWrapper(defaultUsers)
    });

    const avatarButton = screen.getByRole('button');
    await user.click(avatarButton);

    await screen.findByRole('combobox', { name: 'user.list.label' });

    const clearButton = await screen.findByLabelText(/clear/i);
    await user.click(clearButton);

    expect(onChange).toHaveBeenCalledWith([]);
  });

  it('renders and opens with empty users context without crashing', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(<UserList i18nLabel="user.list.label" userIds={['analystA']} onChange={onChange} />, {
      wrapper: createWrapper({})
    });

    expect(screen.getByText('analystA')).toBeInTheDocument();

    const avatarButton = screen.getByRole('button');
    await user.click(avatarButton);

    const combo = await screen.findByRole('combobox', { name: 'user.list.label' });
    await user.click(combo);

    expect(screen.queryAllByRole('option')).toHaveLength(0);
  });
});
