/// <reference types="vitest" />
import { act, render, screen } from '@testing-library/react';
import { useContext } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockUserGet = vi.hoisted(() => vi.fn());
const mockAvatarGet = vi.hoisted(() => vi.fn());

vi.mock('api', () => ({
  default: {
    user: {
      get: mockUserGet,
      avatar: { get: mockAvatarGet }
    }
  }
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

import AvatarProvider, { AvatarContext } from './AvatarProvider';

const Consumer = () => {
  const ctx = useContext(AvatarContext);
  return (
    <div>
      <button onClick={() => void ctx.getAvatar('alice').then(v => (document.body.dataset.value = v))}>load-alice</button>
      <button onClick={() => void ctx.getAvatar('bob').then(v => (document.body.dataset.value = v))}>load-bob</button>
      <button onClick={() => void ctx.getAvatar('').then(v => (document.body.dataset.empty = v))}>empty</button>
    </div>
  );
};

describe('AvatarProvider', () => {
  beforeEach(() => {
    document.body.dataset.value = '';
    document.body.dataset.empty = '';
    mockDispatchApi.mockReset();
    mockUserGet.mockReset();
    mockAvatarGet.mockReset();
  });

  it('returns empty avatars for blank ids and caches resolved avatar lookups', async () => {
    mockDispatchApi.mockResolvedValue('avatar-url');
    render(
      <AvatarProvider>
        <Consumer />
      </AvatarProvider>
    );

    await act(async () => screen.getByText('empty').click());
    expect(document.body.dataset.empty).toBe('');

    await act(async () => screen.getByText('load-alice').click());
    expect(document.body.dataset.value).toBe('avatar-url');
    await act(async () => screen.getByText('load-alice').click());
    expect(mockDispatchApi).toHaveBeenCalledTimes(1);
  });

  it('falls back to the user name when the avatar request returns nothing or throws', async () => {
    mockUserGet.mockResolvedValue({ name: 'Alice Name' });
    mockDispatchApi.mockResolvedValueOnce(undefined).mockRejectedValueOnce(new Error('boom'));
    render(
      <AvatarProvider>
        <Consumer />
      </AvatarProvider>
    );

    await act(async () => screen.getByText('load-bob').click());
    expect(document.body.dataset.value).toBe('Alice Name');
  });
});
