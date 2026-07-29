import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { UserListContext } from 'components/app/providers/UserListProvider';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MembershipManagement } from './MembershipManagement';

const { dispatchApiMock, permissionPutMock, searchUsersMock } = vi.hoisted(() => ({
  dispatchApiMock: vi.fn(),
  permissionPutMock: vi.fn(),
  searchUsersMock: vi.fn()
}));

vi.mock('@tui/core', () => ({
  useAppUser: () => ({
    user: {
      username: 'owner',
      roles: ['admin']
    }
  })
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
        put: permissionPutMock
      }
    },
    search: {
      action: {
        post: () => ({ request: 'get-action' })
      }
    }
  }
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({
    dispatchApi: dispatchApiMock
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
  beforeEach(() => {
    permissionPutMock.mockReset();
    dispatchApiMock.mockReset();
    searchUsersMock.mockReset();

    permissionPutMock.mockImplementation((_id, data) => ({ request: 'grant-permission', data }));
    dispatchApiMock.mockImplementation(async request => {
      if (request.request === 'get-action') {
        return {
          items: [
            {
              owner: 'owner',
              admins: [],
              members: []
            }
          ]
        };
      }

      if (request.request === 'grant-permission') {
        return {
          owner: 'owner',
          admins: [],
          members: ['analyst']
        };
      }
    });
  });

  it('grants a selected member with the batched permission payload', async () => {
    const user = userEvent.setup();

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
        <MembershipManagement open onClose={vi.fn()} />
      </UserListContext.Provider>
    );

    await screen.findAllByText('owner');

    await user.click(screen.getByRole('button', { name: 'Select analyst' }));
    await user.click(screen.getByRole('combobox', { name: 'route.action.privilege.privilege' }));
    await user.click(
      within(await screen.findByRole('listbox')).getByRole('option', {
        name: 'route.actions.privilege.members'
      })
    );
    await user.click(screen.getByRole('button', { name: 'add' }));

    await waitFor(() => {
      expect(permissionPutMock).toHaveBeenCalledWith('action-id', {
        privilege: 'members',
        user_ids: ['analyst']
      });
    });
    expect(await screen.findByText('Analyst')).toBeInTheDocument();
  });
});
