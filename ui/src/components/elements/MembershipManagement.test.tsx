/// <reference types="vitest" />
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MembershipManagement } from './MembershipManagement';

type EntityState = {
  owner?: string;
  admins?: string[];
  members?: string[];
};

let entityState: EntityState;
const dispatchApiMock = vi.fn();

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key
  })
}));

vi.mock('commons/components/app/hooks', () => ({
  useAppUser: () => ({
    user: {
      username: 'owner1',
      roles: ['admin']
    }
  })
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({
    dispatchApi: dispatchApiMock
  })
}));

vi.mock('components/hooks/useMyUserList', () => ({
  default: (ids: Set<string>) => {
    const users: Record<string, { name: string; email: string }> = {};
    ids.forEach(id => {
      users[id] = {
        name: `Name ${id}`,
        email: `${id}@example.com`
      };
    });
    return users;
  }
}));

vi.mock('./display/HowlerAvatar', () => ({
  default: ({ userId }: { userId: string }) => <div data-testid="howler-avatar">{userId}</div>
}));

vi.mock('./UserList', () => ({
  default: ({ onChangeSelectedUserIds }: { onChangeSelectedUserIds?: (userIds: string[]) => void }) => (
    <button onClick={() => onChangeSelectedUserIds?.(['new1', 'new2'])}>mock-select-users</button>
  )
}));

vi.mock('api', () => ({
  default: {
    action: {
      get: (id: string) => ({ __op: 'get', id }),
      permission: {
        putMany: (id: string, payload: { user_id: string[]; privilege: 'owner' | 'admins' | 'members' }) => ({
          __op: 'putMany',
          id,
          payload
        }),
        put: (id: string, payload: { user_id: string; privilege: 'owner' | 'admins' | 'members' }) => ({
          __op: 'put',
          id,
          payload
        }),
        delete: (id: string, payload: { user_id: string; privilege: string }) => ({ __op: 'delete', id, payload })
      }
    }
  }
}));

describe('MembershipManagement', () => {
  beforeEach(() => {
    entityState = {
      owner: 'owner1',
      admins: ['admin1'],
      members: ['member1']
    };

    dispatchApiMock.mockReset();
    dispatchApiMock.mockImplementation(async (request: any) => {
      if (request?.__op === 'get') {
        return {
          owner: entityState.owner,
          admins: [...(entityState.admins || [])],
          members: [...(entityState.members || [])]
        };
      }

      if (request?.__op === 'put') {
        const { user_id: userId, privilege } = request.payload;

        if (privilege === 'owner') {
          entityState.owner = userId;
        } else if (privilege === 'admins') {
          entityState.admins = Array.from(new Set([...(entityState.admins || []), userId]));
        } else {
          entityState.members = Array.from(new Set([...(entityState.members || []), userId]));
        }

        return { ok: true };
      }

      if (request?.__op === 'putMany') {
        const { user_id: userIds, privilege } = request.payload;

        userIds.forEach((userId: string) => {
          if (privilege === 'owner') {
            entityState.owner = userId;
          } else if (privilege === 'admins') {
            entityState.admins = Array.from(new Set([...(entityState.admins || []), userId]));
          } else {
            entityState.members = Array.from(new Set([...(entityState.members || []), userId]));
          }
        });

        return { ok: true };
      }

      if (request?.__op === 'delete') {
        const { user_id: userId, privilege } = request.payload;
        if (privilege === 'admins') {
          entityState.admins = (entityState.admins || []).filter(id => id !== userId);
        }
        if (privilege === 'members') {
          entityState.members = (entityState.members || []).filter(id => id !== userId);
        }
        if (privilege === 'owner' && entityState.owner === userId) {
          entityState.owner = undefined;
        }

        return { ok: true };
      }

      return null;
    });
  });

  it('filters current members by membership role aliases', async () => {
    const user = userEvent.setup();

    render(<MembershipManagement open onClose={vi.fn()} entityId="entity-1" entityType="action" />);

    await waitFor(() => {
      expect(screen.getByText('Name admin1')).toBeInTheDocument();
      expect(screen.getByText('Name member1')).toBeInTheDocument();
    });

    const searchInput = screen.getByLabelText('search');
    await user.clear(searchInput);
    await user.type(searchInput, 'administrator');

    expect(screen.getByText('Name admin1')).toBeInTheDocument();
    expect(screen.queryByText('Name member1')).not.toBeInTheDocument();

    await user.clear(searchInput);
    await user.type(searchInput, 'member');

    expect(screen.getByText('Name member1')).toBeInTheDocument();
    expect(screen.queryByText('Name admin1')).not.toBeInTheDocument();
  });

  it('adds multiple users and refreshes members list with confirmation', async () => {
    const user = userEvent.setup();

    render(<MembershipManagement open onClose={vi.fn()} entityId="entity-1" entityType="action" />);

    await waitFor(() => {
      expect(screen.getByText('Name owner1')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('tab', { name: 'add' }));
    await user.click(screen.getByRole('button', { name: 'mock-select-users' }));

    await user.click(screen.getByRole('combobox', { name: 'privilege' }));
    const listbox = await screen.findByRole('listbox');
    await user.click(within(listbox).getByRole('option', { name: 'members' }));

    await user.click(screen.getByRole('button', { name: 'add' }));

    await waitFor(() => {
      expect(screen.getByText(/members: add OK/i)).toBeInTheDocument();
      expect(screen.getByText('Name new1')).toBeInTheDocument();
      expect(screen.getByText('Name new2')).toBeInTheDocument();
    });

    const putManyCalls = dispatchApiMock.mock.calls.filter(call => call[0]?.__op === 'putMany');
    expect(putManyCalls).toHaveLength(1);
    expect(putManyCalls[0][0].payload.user_id.sort()).toEqual(['new1', 'new2']);

    const putCalls = dispatchApiMock.mock.calls.filter(call => call[0]?.__op === 'put');
    expect(putCalls).toHaveLength(0);
  });

  it('removes a member and refreshes the list', async () => {
    const user = userEvent.setup();

    render(<MembershipManagement open onClose={vi.fn()} entityId="entity-1" entityType="action" />);

    await waitFor(() => {
      expect(screen.getByText('Name member1')).toBeInTheDocument();
    });

    const memberRow = screen.getByText('Name member1').closest('li');
    expect(memberRow).toBeTruthy();

    const removeButton = within(memberRow as HTMLElement).getByRole('button');
    await user.click(removeButton);

    await waitFor(() => {
      expect(screen.queryByText('Name member1')).not.toBeInTheDocument();
    });

    const deleteCalls = dispatchApiMock.mock.calls.filter(call => call[0]?.__op === 'delete');
    expect(deleteCalls).toHaveLength(1);
    expect(deleteCalls[0][0].payload).toEqual({ user_id: 'member1', privilege: 'members' });
  });
});
