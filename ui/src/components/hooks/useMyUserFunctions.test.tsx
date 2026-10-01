/// <reference types="vitest" />
import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockShowSuccessMessage = vi.hoisted(() => vi.fn());
const mockShowWarningMessage = vi.hoisted(() => vi.fn());
const mockNavigate = vi.hoisted(() => vi.fn());
const mockSetUser = vi.hoisted(() => vi.fn());
const mockDrawerOpen = vi.hoisted(() => vi.fn());
const mockShowModal = vi.hoisted(() => vi.fn((node: any) => node.props.onConfirm()));
const mockUserPut = vi.hoisted(() => vi.fn((username: string, body: any) => ({ username, body })));
const mockApiKeyDelete = vi.hoisted(() => vi.fn((keyId: string) => ({ keyId })));
const mockGroupsGet = vi.hoisted(() => ({ groups: true }));

let currentUser = { username: 'current', apikeys: [['existing', ['r'], '2026-12-31']], dashboard: [] } as any;
const modalContextToken = vi.hoisted(() => ({ name: 'modal-context' }));
const drawerContextToken = vi.hoisted(() => ({ name: 'drawer-context' }));

vi.mock('@tui/core', () => ({
  useAppUser: () => ({ user: currentUser, setUser: mockSetUser })
}));

vi.mock('api', () => ({
  default: {
    user: {
      put: mockUserPut,
      groups: { get: () => mockGroupsGet }
    },
    auth: {
      apikey: { del: mockApiKeyDelete }
    }
  }
}));

vi.mock('components/app/drawers/ApiKeyDrawer', () => ({
  default: ({ onCreated }: any) => (
    <button onClick={() => onCreated('new-key', ['rw'], '2027-01-01')}>create api key</button>
  )
}));

vi.mock('components/app/drawers/ViewGroupsDrawer', () => ({
  default: ({ groups }: any) => <div>{groups.join(',')}</div>
}));

vi.mock('components/app/providers/AppDrawerProvider', () => ({
  AppDrawerContext: drawerContextToken
}));

vi.mock('components/app/providers/ModalProvider', () => ({
  ModalContext: modalContextToken
}));

vi.mock('components/elements/display/modals/ConfirmDeleteModal', () => ({
  default: ({ onConfirm }: any) => <button onClick={onConfirm}>confirm delete</button>
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('components/hooks/useMySnackbar', () => ({
  default: () => ({
    showSuccessMessage: mockShowSuccessMessage,
    showWarningMessage: mockShowWarningMessage
  })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-router', () => ({
  useNavigate: () => mockNavigate
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === modalContextToken) {
        return { showModal: mockShowModal };
      }
      if (context === drawerContextToken) {
        return { open: mockDrawerOpen };
      }
      return actual.useContext(context);
    }
  };
});

import useMyUserFunctions from './useMyUserFunctions';

describe('useMyUserFunctions', () => {
  beforeEach(() => {
    currentUser = { username: 'current', apikeys: [['existing', ['r'], '2026-12-31']], dashboard: [] } as any;
    mockDispatchApi.mockReset();
    mockShowSuccessMessage.mockReset();
    mockShowWarningMessage.mockReset();
    mockNavigate.mockReset();
    mockSetUser.mockReset();
    mockDrawerOpen.mockReset();
    mockShowModal.mockReset();
    mockUserPut.mockReset();
    vi.useRealTimers();
  });

  it('updates user profile fields and roles', async () => {
    const { result } = renderHook(() => useMyUserFunctions());
    const user = { username: 'demo', roles: ['member'], apikeys: [] } as any;

    await expect(result.current.editName(user, 'Demo User')).resolves.toEqual({ ...user, name: 'Demo User' });
    await expect(result.current.editQuota(user, '42')).resolves.toEqual({ ...user, api_quota: 42 });
    await expect(result.current.editQuota(user)).resolves.toEqual({ ...user, api_quota: 25 });
    await expect(result.current.addRole(user, 'admin')).resolves.toEqual({ ...user, roles: ['member', 'admin'] });
    await expect(result.current.removeRole({ ...user, roles: ['member', 'admin'] }, 'admin')).resolves.toEqual({
      ...user,
      roles: ['member']
    });

    expect(mockShowSuccessMessage).toHaveBeenCalledWith('api.user.name.updated');
    expect(mockShowSuccessMessage).toHaveBeenCalledWith('api.user.quota.updated');
    expect(mockShowSuccessMessage).toHaveBeenCalledWith('api.user.role.updated');
  });

  it('opens drawers for api keys and group viewing', async () => {
    const { result } = renderHook(() => useMyUserFunctions());

    result.current.addApiKey();
    const apiKeyDrawerProps = mockDrawerOpen.mock.calls[0][0];
    expect(apiKeyDrawerProps.titleKey).toBe('app.drawer.user.apikey.title');

    const apiKeyChild = apiKeyDrawerProps.children;
    apiKeyChild.props.onCreated('new-key', ['rw'], '2027-01-01');
    expect(mockSetUser).toHaveBeenCalledWith({
      ...currentUser,
      apikeys: [...currentUser.apikeys, ['new-key', ['rw'], '2027-01-01']]
    });
    expect(mockShowSuccessMessage).toHaveBeenCalledWith('api.user.apikey.updated');

    mockDispatchApi.mockResolvedValueOnce([]);
    await result.current.viewGroups();
    expect(mockShowWarningMessage).toHaveBeenCalledWith('api.user.groups.empty');

    mockDispatchApi.mockResolvedValueOnce(['group-a', 'group-b']);
    await result.current.viewGroups();
    expect(mockDrawerOpen).toHaveBeenLastCalledWith(
      expect.objectContaining({ titleKey: 'app.drawer.user.groups.title', children: expect.any(Object) })
    );
  });

  it('removes api keys, updates dashboard settings, and logs out after password changes', async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useMyUserFunctions());
    const user = { username: 'demo', roles: ['member'], apikeys: [['key-1', ['r'], '2026-01-01']] } as any;

    await result.current.removeApiKey(user, ['key-1', ['r'], '2026-01-01']);
    expect(mockShowModal).toHaveBeenCalled();
    expect(mockApiKeyDelete).toHaveBeenCalledWith('key-1');
    expect(mockShowSuccessMessage).toHaveBeenCalledWith('api.user.apikey.removed');

    await result.current.setDashboard([{ i: 'widget' }] as any);
    await result.current.setRefreshRate(30);
    await result.current.editPassword('new-pass');
    expect(mockShowSuccessMessage).toHaveBeenCalledWith('password.success');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(mockNavigate).toHaveBeenCalledWith('/logout');
  });
});
