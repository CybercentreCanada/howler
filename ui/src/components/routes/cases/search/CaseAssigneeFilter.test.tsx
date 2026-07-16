/// <reference types="vitest" />
import { render, screen, waitFor } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import { UserListContext } from 'components/app/providers/UserListProvider';
import i18n from 'i18n';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { PropsWithChildren } from 'react';
import { I18nextProvider } from 'react-i18next';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CaseAssigneeFilter from './CaseAssigneeFilter';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

// ---------------------------------------------------------------------------
// Hoisted mocks
// ---------------------------------------------------------------------------

vi.mock('commons/components/app/hooks/useAppUser', () => ({
  useAppUser: () => ({ user: { username: 'alice', name: 'Alice Smith' } as HowlerUser })
}));

// Stub HowlerAvatar to avoid avatar API calls
vi.mock('components/elements/display/HowlerAvatar', () => ({
  default: ({ userId }: { userId: string }) => <div id={`avatar-${userId}`}>{userId}</div>
}));

// Stub UserList to a simple multi-select so we can test the onChange wire-up
// without pulling in the full component and its popover.
vi.mock('components/elements/UserList', () => ({
  default: ({
    userIds,
    onChange,
    multiple
  }: {
    userIds: string[];
    onChange: (v: string[]) => void;
    multiple?: boolean;
  }) => (
    <div id="user-list">
      <button id="user-list-add" onClick={() => onChange([...userIds, 'bob'])}>
        Add bob
      </button>
      {multiple &&
        userIds.map(id => (
          <button key={id} id={`remove-${id}`} onClick={() => onChange(userIds.filter(u => u !== id))}>
            Remove {id}
          </button>
        ))}
    </div>
  )
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockSearchUsers = vi.fn();

const USERS: Record<string, HowlerUser> = {
  alice: { username: 'alice', name: 'Alice Smith' } as HowlerUser,
  bob: { username: 'bob', name: 'Bob Jones' } as HowlerUser
};

const Wrapper = ({ children }: PropsWithChildren) => (
  <I18nextProvider i18n={i18n as any}>
    <UserListContext.Provider value={{ users: USERS, searchUsers: mockSearchUsers, fetchUsers: vi.fn() } as any}>
      {children}
    </UserListContext.Provider>
  </I18nextProvider>
);

const renderFilter = (assigneeFilter: string[], onChange = vi.fn()) =>
  render(<CaseAssigneeFilter assigneeFilter={assigneeFilter} onChange={onChange} />, { wrapper: Wrapper });

const openPopper = async (user: UserEvent, labelText: string) => {
  const chip = screen.getByText(labelText).closest('.MuiChip-root');
  await user.click(chip);
  await waitFor(() => {
    expect(screen.getByTestId('user-list')).toBeInTheDocument();
  });
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('CaseAssigneeFilter', () => {
  let user: UserEvent;

  beforeEach(() => {
    user = userEvent.setup();
    vi.clearAllMocks();
  });

  describe('searchUsers on mount', () => {
    it('calls searchUsers with "uname:*" on mount', () => {
      renderFilter([]);
      expect(mockSearchUsers).toHaveBeenCalledWith('uname:*');
    });
  });

  describe('label', () => {
    it('shows the default "Assignee" label when no assignees are selected', () => {
      renderFilter([]);
      expect(screen.getByText(i18n.t('route.cases.filter.assignee'))).toBeInTheDocument();
    });

    it('shows the user display name when one assignee is selected', () => {
      renderFilter(['alice']);
      expect(screen.getByText('Alice Smith')).toBeInTheDocument();
    });

    it('shows count + "Assignees" when multiple assignees are selected', () => {
      renderFilter(['alice', 'bob']);
      expect(screen.getByText(`2 ${i18n.t('route.cases.filter.assignees')}`)).toBeInTheDocument();
    });

    it('falls back to username when user is not in the user map', () => {
      renderFilter(['unknown-user']);
      const chipLabel = document.querySelector('.MuiChip-label');
      expect(chipLabel?.textContent).toContain('unknown-user');
    });
  });

  describe('chip color', () => {
    it('uses default color when no assignees are selected', () => {
      renderFilter([]);
      const chip = screen.getByText(i18n.t('route.cases.filter.assignee')).closest('.MuiChip-root');
      expect(chip).not.toHaveClass('MuiChip-colorPrimary');
    });

    it('uses primary color when assignees are selected', () => {
      renderFilter(['alice']);
      const chip = screen.getByText('Alice Smith').closest('.MuiChip-root');
      expect(chip).toHaveClass('MuiChip-colorPrimary');
    });
  });

  describe('"Myself" checkbox', () => {
    it('is unchecked when the current user is not in the filter', async () => {
      renderFilter([]);
      await openPopper(user, i18n.t('route.cases.filter.assignee'));
      const checkbox = screen.getByRole('checkbox', { name: i18n.t('route.cases.filter.myself') });
      expect(checkbox).not.toBeChecked();
    });

    it('is checked when the current user is already in the filter', async () => {
      renderFilter(['alice']);
      await openPopper(user, 'Alice Smith');
      const checkbox = screen.getByRole('checkbox', { name: i18n.t('route.cases.filter.myself') });
      expect(checkbox).toBeChecked();
    });

    it('adds the current user to the filter when the checkbox is checked', async () => {
      const onChange = vi.fn();
      renderFilter([], onChange);
      await openPopper(user, i18n.t('route.cases.filter.assignee'));
      await user.click(screen.getByRole('checkbox', { name: i18n.t('route.cases.filter.myself') }));
      expect(onChange).toHaveBeenCalledWith(['alice']);
    });

    it('removes the current user from the filter when the checkbox is unchecked', async () => {
      const onChange = vi.fn();
      renderFilter(['alice', 'bob'], onChange);
      await openPopper(user, `2 ${i18n.t('route.cases.filter.assignees')}`);
      await user.click(screen.getByRole('checkbox', { name: i18n.t('route.cases.filter.myself') }));
      expect(onChange).toHaveBeenCalledWith(['bob']);
    });
  });

  describe('UserList onChange passthrough', () => {
    it('passes onChange directly to UserList', async () => {
      const onChange = vi.fn();
      renderFilter(['alice'], onChange);
      await openPopper(user, 'Alice Smith');
      await user.click(screen.getByTestId('user-list-add'));
      expect(onChange).toHaveBeenCalledWith(['alice', 'bob']);
    });
  });
});
