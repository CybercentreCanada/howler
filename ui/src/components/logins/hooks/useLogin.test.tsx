/// <reference types="vitest" />
import { renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { StorageKey } from 'utils/constants';

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockSetUser = vi.hoisted(() => vi.fn());
const mockShowErrorMessage = vi.hoisted(() => vi.fn());
const mockShowModal = vi.hoisted(() => vi.fn());
const mockNavigate = vi.hoisted(() => vi.fn());
const mockGet = vi.hoisted(() => vi.fn());
const mockRemove = vi.hoisted(() => vi.fn());
const mockSaveLoginCredential = vi.hoisted(() => vi.fn());
const mockWhoamiGet = vi.hoisted(() => vi.fn(() => ({ url: 'whoami' })));
const mockLoginPost = vi.hoisted(() => vi.fn((body: any) => ({ type: 'login-post', body })));
const mockLoginGet = vi.hoisted(() => vi.fn((params: URLSearchParams) => ({ type: 'login-get', params })));

let locationValue = { pathname: '/login', search: '' };
let searchParamsValue = new URLSearchParams('code=abc');
const modalContextToken = vi.hoisted(() => ({ name: 'modal-context' }));

vi.mock('@tui/core', () => ({
  useAppUser: () => ({ setUser: mockSetUser })
}));

vi.mock('api', () => ({
  default: {
    user: { whoami: { get: mockWhoamiGet } },
    auth: { login: { post: mockLoginPost, get: mockLoginGet } }
  }
}));

vi.mock('components/app/providers/ModalProvider', () => ({
  ModalContext: modalContextToken
}));

vi.mock('components/elements/display/modals/LoginErrorModal', () => ({
  default: ({ error }: any) => <div>{error.message}</div>
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('components/hooks/useMyLocalStorage', () => ({
  default: () => ({ get: mockGet, remove: mockRemove })
}));

vi.mock('components/hooks/useMySnackbar', () => ({
  default: () => ({ showErrorMessage: mockShowErrorMessage })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-router', () => ({
  useLocation: () => locationValue,
  useNavigate: () => mockNavigate,
  useSearchParams: () => [searchParamsValue]
}));

vi.mock('utils/localStorage', () => ({
  saveLoginCredential: mockSaveLoginCredential
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === modalContextToken) {
        return { showModal: mockShowModal };
      }
      return actual.useContext(context);
    }
  };
});

import useLogin from './useLogin';

describe('useLogin', () => {
  beforeEach(() => {
    locationValue = { pathname: '/login', search: '' };
    searchParamsValue = new URLSearchParams('code=abc');
    mockDispatchApi.mockReset();
    mockSetUser.mockReset();
    mockShowErrorMessage.mockReset();
    mockShowModal.mockReset();
    mockNavigate.mockReset();
    mockGet.mockReset();
    mockRemove.mockReset();
    mockSaveLoginCredential.mockReset();
  });

  it('hydrates the user and navigates to stored next location', async () => {
    mockDispatchApi.mockResolvedValueOnce({
      username: 'demo',
      favourite_analytics: undefined
    });
    mockGet.mockImplementation((key: string) => {
      if (key === StorageKey.NEXT_LOCATION) return '/hits/1';
      if (key === StorageKey.NEXT_SEARCH) return '?tab=details';
      return undefined;
    });

    const { result } = renderHook(() => useLogin());
    await result.current.getUser();

    expect(mockDispatchApi).toHaveBeenCalledWith({ url: 'whoami' }, { showError: false, throwError: true });
    expect(mockSetUser).toHaveBeenCalledWith({ username: 'demo', favourite_analytics: [] });
    expect(mockNavigate).toHaveBeenCalledWith('/hits/1?tab=details');
    expect(mockRemove).toHaveBeenCalledWith(StorageKey.NEXT_LOCATION);
    expect(mockRemove).toHaveBeenCalledWith(StorageKey.NEXT_SEARCH);
  });

  it('navigates home on the login route, handles null users, and routes 403 errors to logout', async () => {
    const { result } = renderHook(() => useLogin());

    mockDispatchApi.mockResolvedValueOnce({ username: 'demo', favourite_analytics: ['a'] });
    mockGet.mockReturnValue(undefined);
    await result.current.getUser();
    expect(mockNavigate).toHaveBeenCalledWith('/');

    mockDispatchApi.mockResolvedValueOnce(null);
    await result.current.getUser();
    expect(mockSetUser).toHaveBeenCalledWith(null);
    expect(mockShowErrorMessage).toHaveBeenCalledWith('user.error.failed');

    mockDispatchApi.mockRejectedValueOnce(Object.assign(new Error('forbidden'), { cause: { api_status_code: 403 } }));
    await result.current.getUser();
    expect(mockNavigate).toHaveBeenCalledWith('/logout');
  });

  it('shows the login error modal for non-403 failures', async () => {
    const { result } = renderHook(() => useLogin());

    mockDispatchApi.mockRejectedValueOnce(new Error('network down'));
    await result.current.getUser();

    expect(mockShowModal).toHaveBeenCalled();
    expect(mockShowModal.mock.calls[0][1]).toEqual({ disableClose: true });
  });

  it('performs password and oauth login flows', async () => {
    const { result } = renderHook(() => useLogin());

    mockDispatchApi.mockResolvedValueOnce(null);
    await result.current.doLogin({ user: 'demo', password: 'bad' } as any);
    expect(mockShowErrorMessage).toHaveBeenCalledWith('user.login.failed');

    mockDispatchApi.mockResolvedValueOnce({ access_token: 'token' });
    mockSaveLoginCredential.mockReturnValueOnce(true);
    mockDispatchApi.mockResolvedValueOnce({ username: 'demo', favourite_analytics: [] });
    await result.current.doLogin({ user: 'demo', password: 'good' } as any);
    expect(mockLoginPost).toHaveBeenCalledWith({ user: 'demo', password: 'good' });
    expect(mockSaveLoginCredential).toHaveBeenCalledWith({ access_token: 'token' });

    mockDispatchApi.mockResolvedValueOnce({ access_token: 'oauth' });
    mockSaveLoginCredential.mockReturnValueOnce(true);
    mockDispatchApi.mockResolvedValueOnce({ username: 'oauth-user', favourite_analytics: [] });
    await result.current.doOAuth();
    expect(mockLoginGet).toHaveBeenCalledWith(searchParamsValue);

    mockDispatchApi.mockResolvedValueOnce(null);
    await result.current.doOAuth();
    expect(mockShowErrorMessage).toHaveBeenCalledWith('user.login.failed');
  });
});
