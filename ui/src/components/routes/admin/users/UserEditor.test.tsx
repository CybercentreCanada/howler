/// <reference types="vitest" />
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockUseUserFunctions = vi.hoisted(() => ({
  editName: vi.fn(async (user: any, name: string) => ({ ...user, name })),
  editPassword: vi.fn(),
  editQuota: vi.fn(async (user: any, quota?: string) => ({ ...user, api_quota: quota ? parseInt(quota) : 25 })),
  addRole: vi.fn(async (user: any, role: string) => ({ ...user, roles: [...(user.roles ?? []), role] })),
  removeRole: vi.fn(async (user: any, role: string) => ({ ...user, roles: (user.roles ?? []).filter((r: string) => r !== role) })),
  addApiKey: vi.fn(),
  removeApiKey: vi.fn(async (user: any, key: any) => ({ ...user, apikeys: (user.apikeys ?? []).filter((v: any) => v !== key) })),
  viewGroups: vi.fn()
}));

let currentUser: any = { username: 'admin', is_admin: true };
let paramsValue: any = { id: 'alice' };

vi.mock('@tui/core', () => ({
  useAppUser: () => ({ user: currentUser })
}));

vi.mock('api', () => ({
  default: {
    user: {
      get: (id: string) => ({ id })
    }
  }
}));

vi.mock('components/elements/display/UserPageWrapper', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('components/hooks/useMyUserFunctions', () => ({
  default: () => mockUseUserFunctions
}));

vi.mock('components/routes/settings/ProfileSection', () => ({
  default: (props: any) => (
    <div>
      <span>{`profile:${props.user.username}`}</span>
      <span>{String(!!props.editName)}-{String(!!props.addRole)}-{String(!!props.removeRole)}-{String(!!props.viewGroups)}</span>
    </div>
  )
}));

vi.mock('components/routes/settings/SecuritySection', () => ({
  default: (props: any) => (
    <div>
      <span>{`security:${props.user.username}`}</span>
      <span>{String(!!props.editPassword)}-{String(!!props.addApiKey)}-{String(!!props.removeApiKey)}-{String(!!props.editQuota)}</span>
    </div>
  )
}));

vi.mock('react-router', () => ({
  useParams: () => paramsValue
}));

import UserEditor from './UserEditor';

describe('UserEditor', () => {
  beforeEach(() => {
    currentUser = { username: 'admin', is_admin: true };
    paramsValue = { id: 'alice' };
    mockDispatchApi.mockReset();
  });

  it('loads the requested user and exposes admin controls', async () => {
    mockDispatchApi.mockResolvedValue({ username: 'alice', roles: ['member'], apikeys: [] });
    render(<UserEditor />);

    await waitFor(() => expect(screen.getByText('profile:alice')).toBeInTheDocument());
    expect(screen.getByText('true-true-true-false')).toBeInTheDocument();
    expect(screen.getByText('false-false-true-true')).toBeInTheDocument();
  });

  it('exposes self-service actions for the same user', async () => {
    currentUser = { username: 'alice', is_admin: false };
    mockDispatchApi.mockResolvedValue({ username: 'alice', roles: ['member'], apikeys: [] });
    render(<UserEditor />);

    await waitFor(() => expect(screen.getByText('profile:alice')).toBeInTheDocument());
    expect(screen.getByText('true-false-false-true')).toBeInTheDocument();
    expect(screen.getByText('true-true-true-false')).toBeInTheDocument();
  });
});
