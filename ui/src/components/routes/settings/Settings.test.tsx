/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const mockGet = vi.hoisted(() => vi.fn());
const mockSetUser = vi.hoisted(() => vi.fn());

let currentUser: any = { username: 'alice', is_admin: true, roles: ['admin'] };

vi.mock('@tui/core', () => ({
  useAppUser: () => ({ user: currentUser, setUser: mockSetUser })
}));

vi.mock('components/elements/display/UserPageWrapper', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/hooks/useMyLocalStorage', () => ({
  default: () => ({ get: mockGet })
}));

vi.mock('components/hooks/useMyUserFunctions', () => ({
  default: () => ({
    editName: vi.fn(),
    editPassword: vi.fn(),
    editQuota: vi.fn(),
    addApiKey: vi.fn(),
    removeApiKey: vi.fn(),
    addRole: vi.fn(),
    removeRole: vi.fn(),
    viewGroups: vi.fn()
  })
}));

vi.mock('./AdminSection', () => ({
  default: () => <div>admin-section</div>
}));

vi.mock('./LocalSection', () => ({
  default: () => <div>local-section</div>
}));

vi.mock('./ProfileSection', () => ({
  default: (props: any) => <div>{`profile:${String(!!props.editName)}:${String(!!props.addRole)}:${String(!!props.removeRole)}`}</div>
}));

vi.mock('./SecuritySection', () => ({
  default: (props: any) => <div>{`security:${String(!!props.editPassword)}:${String(!!props.editQuota)}`}</div>
}));

import Settings from './Settings';

describe('Settings', () => {
  it('shows admin controls for local admin users', () => {
    mockGet.mockReturnValue('token');
    currentUser = { username: 'alice', is_admin: true, roles: ['admin'] };
    render(<Settings />);

    expect(screen.getByText('profile:true:true:true')).toBeInTheDocument();
    expect(screen.getByText('security:true:true')).toBeInTheDocument();
    expect(screen.getByText('local-section')).toBeInTheDocument();
    expect(screen.getByText('admin-section')).toBeInTheDocument();
  });

  it('disables oauth-sensitive profile controls and hides admin section for non-admin users', () => {
    mockGet.mockReturnValue('a.b.c');
    currentUser = { username: 'alice', is_admin: false, roles: ['member'] };
    render(<Settings />);

    expect(screen.getByText('profile:false:false:false')).toBeInTheDocument();
    expect(screen.getByText('security:true:false')).toBeInTheDocument();
    expect(screen.queryByText('admin-section')).not.toBeInTheDocument();
  });
});
