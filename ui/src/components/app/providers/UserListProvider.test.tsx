import { act, renderHook } from '@testing-library/react';
import type { HowlerSearchResponse } from 'api/search';
import type { HowlerUser } from 'models/entities/HowlerUser';
import { type PropsWithChildren, useContext } from 'react';
import UserListProvider, { UserListContext } from './UserListProvider';

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockSearchUserPost = vi.hoisted(() => vi.fn());

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('api', () => ({
  default: {
    search: {
      user: {
        post: mockSearchUserPost
      }
    }
  }
}));

const makeUser = (username: string, name = username): HowlerUser => ({
  username,
  name,
  email: `${username}@example.com`,
  type: ['user']
});

const makeResponse = (...users: HowlerUser[]): HowlerSearchResponse<HowlerUser> => ({
  items: users,
  offset: 0,
  rows: users.length,
  total: users.length
});

const Wrapper = ({ children }: PropsWithChildren) => <UserListProvider>{children}</UserListProvider>;

describe('UserListProvider', () => {
  beforeEach(() => {
    mockDispatchApi.mockReset();
    mockSearchUserPost.mockReset();

    mockDispatchApi.mockImplementation(async apiCall => apiCall);
    mockSearchUserPost.mockResolvedValue(makeResponse());
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('initializes with an empty user map', () => {
    const hook = renderHook(() => useContext(UserListContext), { wrapper: Wrapper });

    expect(hook.result.current.users).toEqual({});
  });

  it('searchUsers requests users and merges them into state', async () => {
    const firstUser = makeUser('alpha');
    const updatedFirstUser = makeUser('alpha', 'Alpha Updated');
    const secondUser = makeUser('bravo');

    mockSearchUserPost
      .mockResolvedValueOnce(makeResponse(firstUser))
      .mockResolvedValueOnce(makeResponse(updatedFirstUser, secondUser));

    const hook = renderHook(() => useContext(UserListContext), { wrapper: Wrapper });

    await act(async () => {
      await hook.result.current.searchUsers('name:alpha');
    });

    await act(async () => {
      await hook.result.current.searchUsers('name:(alpha OR bravo)');
    });

    expect(hook.result.current.users).toEqual({
      alpha: updatedFirstUser,
      bravo: secondUser
    });

    expect(mockSearchUserPost).toHaveBeenNthCalledWith(1, { query: 'name:alpha', rows: 1000 });
    expect(mockSearchUserPost).toHaveBeenNthCalledWith(2, { query: 'name:(alpha OR bravo)', rows: 1000 });
    expect(mockDispatchApi).toHaveBeenCalledWith(expect.any(Promise), {
      throwError: false,
      logError: false,
      showError: false
    });
  });

  it('leaves the current users unchanged when the search returns no response', async () => {
    const alpha = makeUser('alpha');
    mockDispatchApi.mockResolvedValueOnce(makeResponse(alpha)).mockResolvedValueOnce(undefined);

    const hook = renderHook(() => useContext(UserListContext), { wrapper: Wrapper });

    await act(async () => {
      await hook.result.current.searchUsers('name:alpha');
      await hook.result.current.searchUsers('name:bravo');
    });

    expect(hook.result.current.users).toEqual({ alpha });
  });

  it('fetchUsers resets the debounce timer and batches unique ids', async () => {
    vi.useFakeTimers();

    const hook = renderHook(() => useContext(UserListContext), { wrapper: Wrapper });

    act(() => {
      hook.result.current.fetchUsers(new Set(['alpha']));
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    act(() => {
      hook.result.current.fetchUsers(new Set(['alpha', 'bravo']));
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(199);
    });

    expect(mockSearchUserPost).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });

    expect(mockSearchUserPost).toHaveBeenCalledWith({ query: 'id:alpha OR bravo', rows: 1000 });
  });

  it('fetchUsers excludes Unknown and skips users that are already loaded', async () => {
    vi.useFakeTimers();

    const alpha = makeUser('alpha');
    const bravo = makeUser('bravo');
    mockSearchUserPost.mockResolvedValueOnce(makeResponse(alpha)).mockResolvedValueOnce(makeResponse(bravo));

    const hook = renderHook(() => useContext(UserListContext), { wrapper: Wrapper });

    await act(async () => {
      await hook.result.current.searchUsers('id:alpha');
    });

    act(() => {
      hook.result.current.fetchUsers(new Set(['Unknown', 'alpha', 'bravo']));
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(200);
    });

    expect(mockSearchUserPost).toHaveBeenCalledTimes(2);
    expect(mockSearchUserPost).toHaveBeenNthCalledWith(2, { query: 'id:bravo', rows: 1000 });
    expect(hook.result.current.users).toEqual({ alpha, bravo });
  });

  it('does not search when every requested id is excluded or already loaded', async () => {
    vi.useFakeTimers();

    const alpha = makeUser('alpha');
    mockDispatchApi.mockResolvedValueOnce(makeResponse(alpha));

    const hook = renderHook(() => useContext(UserListContext), { wrapper: Wrapper });

    await act(async () => {
      await hook.result.current.searchUsers('id:alpha');
    });

    act(() => {
      hook.result.current.fetchUsers(new Set(['Unknown', 'alpha']));
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(200);
    });

    expect(mockSearchUserPost).toHaveBeenCalledTimes(1);
  });

  it('clears pending debounce timer on unmount', () => {
    vi.useFakeTimers();

    const hook = renderHook(() => useContext(UserListContext), { wrapper: Wrapper });

    act(() => {
      hook.result.current.fetchUsers(new Set(['charlie']));
    });

    hook.unmount();

    act(() => {
      vi.advanceTimersByTime(200);
    });

    expect(mockSearchUserPost).not.toHaveBeenCalled();
  });
});
