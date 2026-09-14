import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { UserListContext } from 'components/app/providers/UserListProvider';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MembershipManagement } from './membership/MembershipManagement';
import type { Ownership } from './membership/types';

const {
  appUserMock,
  dispatchApiMock,
  permissionDeleteMock,
  permissionPutMock,
  searchUsersMock,
  showErrorMessageMock,
  showSuccessMessageMock
} = vi.hoisted(() => ({
  appUserMock: vi.fn(),
  dispatchApiMock: vi.fn(),
  permissionDeleteMock: vi.fn(),
  permissionPutMock: vi.fn(),
  searchUsersMock: vi.fn(),
  showErrorMessageMock: vi.fn(),
  showSuccessMessageMock: vi.fn()
}));

vi.mock('@tui/core', () => ({
  useAppUser: appUserMock
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key
  })
}));

vi.mock('api', () => ({
  default: {
    action: {
      permission: {
        delete: permissionDeleteMock,
        put: permissionPutMock
      }
    }
  }
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({
    dispatchApi: dispatchApiMock
  })
}));

vi.mock('components/hooks/useMySnackbar', () => ({
  default: () => ({
    showErrorMessage: showErrorMessageMock,
    showSuccessMessage: showSuccessMessageMock,
    showWarningMessage: vi.fn()
  })
}));

vi.mock('react-router', () => ({
  useLocation: () => ({ pathname: '/action/action-id' }),
  useParams: () => ({ id: 'action-id' })
}));

vi.mock('./display/HowlerAvatar', () => ({
  default: ({ userId }: { userId: string }) => <span>{userId}</span>
}));

vi.mock('./UserList', () => ({
  default: ({ onChange }: { onChange: (userIds: string[]) => void }) => (
    <button onClick={() => onChange(['analyst'])}>Select analyst</button>
  )
}));

describe('MembershipManagement', () => {
  const entity: Ownership = {
    owner: 'owner',
    admins: [],
    members: []
  };

  const renderMembershipManagement = (overrides: Partial<Ownership> = {}, onChange = vi.fn()) => {
    render(
      <UserListContext.Provider
        value={{
          users: {
            analyst: {
              email: 'analyst@example.com',
              name: 'Analyst',
              type: [],
              username: 'analyst'
            }
          },
          fetchUsers: vi.fn(),
          searchUsers: searchUsersMock
        }}
      >
        <MembershipManagement type="action" entity={{ ...entity, ...overrides }} onChange={onChange} />
      </UserListContext.Provider>
    );

    return onChange;
  };

  beforeEach(() => {
    appUserMock.mockReturnValue({
      user: {
        username: 'owner',
        roles: ['admin']
      }
    });
    permissionPutMock.mockReset();
    permissionDeleteMock.mockReset();
    dispatchApiMock.mockReset();
    searchUsersMock.mockReset();
    showErrorMessageMock.mockReset();
    showSuccessMessageMock.mockReset();

    permissionPutMock.mockImplementation((_id, data) => ({ request: 'grant-permission', data }));
    permissionDeleteMock.mockImplementation((_id, data) => ({ request: 'remove-permission', data }));
    dispatchApiMock.mockImplementation(async request => {
      if (request.request === 'grant-permission') {
        return {
          owner: 'owner',
          admins: [],
          members: ['analyst']
        };
      }

      if (request.request === 'remove-permission') {
        return {
          owner: 'owner',
          admins: [],
          members: []
        };
      }
    });
  });

  it('grants a selected member with the batched permission payload', async () => {
    const user = userEvent.setup();
    const onChange = renderMembershipManagement();

    await user.click(screen.getByRole('button', { name: 'membership.manage' }));
    await user.click(screen.getByRole('button', { name: 'Select analyst' }));
    await user.click(screen.getByRole('button', { name: 'add' }));

    expect(permissionPutMock).toHaveBeenCalledWith('action-id', {
      privilege: 'members',
      user_ids: ['analyst']
    });
    await waitFor(() => expect(onChange).toHaveBeenCalledWith({ owner: 'owner', admins: [], members: ['analyst'] }));
    expect(showSuccessMessageMock).toHaveBeenCalledWith('membership.message.success');
  });

  it('removes the privilege represented by the selected member row', async () => {
    const user = userEvent.setup();
    const onChange = renderMembershipManagement({ admins: ['analyst'] });

    await user.click(screen.getByRole('button', { name: 'membership.manage' }));
    const analystRow = screen.getByText('Analyst').closest('li');
    expect(analystRow).not.toBeNull();

    await user.click(within(analystRow!).getByRole('button'));

    expect(permissionDeleteMock).toHaveBeenCalledWith('action-id', {
      privilege: 'admins',
      user_ids: ['analyst']
    });
    expect(dispatchApiMock).toHaveBeenCalledWith(
      {
        request: 'remove-permission',
        data: { privilege: 'admins', user_ids: ['analyst'] }
      },
      { throwError: false }
    );
    await waitFor(() => expect(onChange).toHaveBeenCalledWith({ owner: 'owner', admins: [], members: [] }));
    expect(showSuccessMessageMock).toHaveBeenCalledWith('membership.message.success');
  });

  it('offers owner transfer only to the owner or a global admin', async () => {
    const user = userEvent.setup();
    renderMembershipManagement();

    await user.click(screen.getByRole('button', { name: 'membership.manage' }));
    expect(screen.getByRole('button', { name: 'membership.privilege.owner' })).toBeInTheDocument();
  });

  it('does not offer owner transfer to a local admin', async () => {
    const user = userEvent.setup();
    appUserMock.mockReturnValue({
      user: {
        username: 'admin',
        roles: []
      }
    });

    renderMembershipManagement({ admins: ['admin'] });
    await user.click(screen.getByRole('button', { name: 'membership.manage' }));
    expect(screen.queryByRole('button', { name: 'membership.privilege.owner' })).not.toBeInTheDocument();
  });

  it('does not render membership controls for an unrelated user', () => {
    appUserMock.mockReturnValue({
      user: {
        username: 'analyst',
        roles: []
      }
    });

    renderMembershipManagement();

    expect(screen.queryByRole('button', { name: 'membership.manage' })).not.toBeInTheDocument();
  });

  it('shows an error when adding a member fails', async () => {
    const user = userEvent.setup();
    dispatchApiMock.mockRejectedValueOnce(new Error('request failed'));
    renderMembershipManagement();

    await user.click(screen.getByRole('button', { name: 'membership.manage' }));
    await user.click(screen.getByRole('button', { name: 'Select analyst' }));
    await user.click(screen.getByRole('button', { name: 'add' }));

    await waitFor(() => expect(showErrorMessageMock).toHaveBeenCalledWith('membership.message.error'));
    expect(showSuccessMessageMock).not.toHaveBeenCalled();
  });
});
