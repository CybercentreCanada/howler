/// <reference types="vitest" />
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { UserListContext } from 'components/app/providers/UserListProvider';
import i18n from 'i18n';
import React, { type ReactNode } from 'react';
import { I18nextProvider } from 'react-i18next';
import { describe, expect, it, vi } from 'vitest';
import UserList from './UserList';

vi.mock('./display/HowlerAvatar', () => ({
  default: ({ userId }: { userId: string }) => <div data-testid="howler-avatar">{userId}</div>
}));

type WrapperProps = {
  children: ReactNode;
  users?: Record<string, any>;
  searchUsers?: ReturnType<typeof vi.fn>;
};

const renderWithProviders = ({
  children,
  users = {
    alice: { username: 'alice', name: 'Alice Example', email: 'alice@example.com' },
    bob: { username: 'bob', name: 'Bob Example', email: 'bob@example.com' }
  },
  searchUsers = vi.fn()
}: WrapperProps) => {
  const contextValue = {
    users,
    searchUsers,
    fetchUsers: vi.fn()
  };

  return {
    ...render(
      <I18nextProvider i18n={i18n as any}>
        <UserListContext.Provider value={contextValue as any}>{children}</UserListContext.Provider>
      </I18nextProvider>
    ),
    searchUsers
  };
};

describe('UserList', () => {
  it('preserves legacy trigger by default (IconButton mode)', () => {
    renderWithProviders({
      children: <UserList userId="alice" onChange={vi.fn()} i18nLabel="username" />
    });

    const triggerButton = screen.getByRole('button');
    expect(triggerButton).toHaveClass('MuiIconButton-root');
    expect(screen.queryByText('Alice Example')).not.toBeInTheDocument();
  });

  it('searches users on mount with default query', async () => {
    const { searchUsers } = renderWithProviders({
      children: <UserList userId="alice" onChange={vi.fn()} i18nLabel="username" />
    });

    await waitFor(() => {
      expect(searchUsers).toHaveBeenCalledWith('uname:*');
      expect(searchUsers).toHaveBeenCalledTimes(1);
    });
  });

  it('opens the picker popover when legacy trigger is clicked', async () => {
    const user = userEvent.setup();

    renderWithProviders({
      children: <UserList userId="alice" onChange={vi.fn()} i18nLabel="username" />
    });

    await user.click(screen.getByRole('button'));

    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });

  it('renders modified mode as an inline editable combobox', () => {
    renderWithProviders({
      children: <UserList userId="alice" onChange={vi.fn()} i18nLabel="username" isModified />
    });

    expect(screen.queryByRole('button')).not.toBeInTheDocument();
    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });

  it('updates value directly while typing in modified mode', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    const StatefulModifiedUserList = () => {
      const [value, setValue] = React.useState('');
      return (
        <UserList
          userId={value}
          onChange={nextValue => {
            setValue(nextValue);
            onChange(nextValue);
          }}
          i18nLabel="username"
          isModified
        />
      );
    };

    renderWithProviders({
      children: <StatefulModifiedUserList />
    });

    const input = screen.getByRole('combobox');
    await user.type(input, 'ali');

    expect(onChange).toHaveBeenCalled();
    expect(onChange.mock.calls.some(call => call[0] === 'ali')).toBe(true);
  });

  it('shows and updates avatar in modified mode while editing', async () => {
    const user = userEvent.setup();

    const StatefulModifiedUserList = () => {
      const [value, setValue] = React.useState('alice');
      return <UserList userId={value} onChange={setValue} i18nLabel="username" isModified />;
    };

    renderWithProviders({
      children: <StatefulModifiedUserList />
    });

    const input = screen.getByRole('combobox');
    const autocompleteRoot = input.closest('.MuiAutocomplete-root') as HTMLElement;
    const getInlineAvatar = () => autocompleteRoot.querySelector('[data-testid="howler-avatar"]');

    expect(getInlineAvatar()).not.toBeNull();
    expect(getInlineAvatar()).toHaveTextContent('alice');

    await user.click(input);
    await user.keyboard('{Control>}a{/Control}{Backspace}unknown-user');

    await waitFor(() => {
      expect(getInlineAvatar()).not.toBeNull();
      expect(getInlineAvatar()).toHaveTextContent('unknown-user');
    });
  });

  it('allows selecting an option directly in modified mode', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    renderWithProviders({
      users: { bob: { username: 'bob', name: 'Bob Example', email: 'bob@example.com' } },
      children: <UserList userId="" onChange={onChange} i18nLabel="username" isModified />
    });

    await user.click(screen.getByRole('combobox'));

    const listbox = await screen.findByRole('listbox');
    await user.click(within(listbox).getByRole('option'));

    expect(onChange).toHaveBeenCalledWith('bob');
  });

  it('supports multiple selected users in modified mode with removable chips', async () => {
    const user = userEvent.setup();

    const StatefulMultiUserList = () => {
      const [value, setValue] = React.useState<string[]>(['alice']);
      return (
        <UserList
          i18nLabel="username"
          isModified
          allowMultiple
          selectedUserIds={value}
          onChangeSelectedUserIds={setValue}
        />
      );
    };

    renderWithProviders({
      children: <StatefulMultiUserList />
    });

    expect(screen.getAllByText('alice').length).toBeGreaterThan(0);

    const input = screen.getByRole('combobox');
    await user.click(input);
    const listbox = await screen.findByRole('listbox');
    await user.click(within(listbox).getByRole('option', { name: /bob/i }));

    expect(screen.getAllByText('bob').length).toBeGreaterThan(0);

    const deleteIcons = document.querySelectorAll('.MuiChip-deleteIcon');
    expect(deleteIcons.length).toBeGreaterThan(0);
    await user.click(deleteIcons[0] as HTMLElement);

    await waitFor(() => {
      expect(screen.queryByText('alice', { selector: '.MuiChip-label' })).not.toBeInTheDocument();
    });
  });

  it('supports non-modified multiple mode with userIds via popover picker', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    const StatefulMultiPopoverUserList = () => {
      const [value, setValue] = React.useState<string[]>(['alice']);

      return (
        <UserList
          i18nLabel="username"
          multiple
          userIds={value}
          onChange={(nextValue: string[] | string) => {
            const normalized = Array.isArray(nextValue) ? nextValue : [nextValue].filter(Boolean);
            setValue(normalized);
            onChange(normalized);
          }}
        />
      );
    };

    renderWithProviders({
      users: {
        alice: { username: 'alice', name: 'Alice Example', email: 'alice@example.com' },
        bob: { username: 'bob', name: 'Bob Example', email: 'bob@example.com' }
      },
      children: <StatefulMultiPopoverUserList />
    });

    expect(screen.getByText('alice')).toBeInTheDocument();

    await user.click(screen.getByRole('button'));
    await user.click(screen.getByRole('combobox'));

    const listbox = await screen.findByRole('listbox');
    await user.click(within(listbox).getByRole('option', { name: /bob/i }));

    expect(onChange).toHaveBeenCalled();
    expect(onChange.mock.calls.some(call => call[0].includes('alice') && call[0].includes('bob'))).toBe(true);
  });

  it('calls onChange with selected user id from picker', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    renderWithProviders({
      users: { bob: { username: 'bob', name: 'Bob Example', email: 'bob@example.com' } },
      children: <UserList userId="" onChange={onChange} i18nLabel="username" />
    });

    await user.click(screen.getByRole('button'));
    await user.click(screen.getByRole('combobox'));

    const listbox = await screen.findByRole('listbox');
    await user.click(within(listbox).getByRole('option'));

    expect(onChange).toHaveBeenCalledWith('bob');
  });
});
