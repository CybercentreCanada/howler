/// <reference types="vitest" />
import { act, renderHook, waitFor } from '@testing-library/react';
import { useContext } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockAnalyticGet = vi.hoisted(() => vi.fn());
const mockAnalyticSearchPost = vi.hoisted(() => vi.fn());

let userReady = true;

vi.mock('@tui/core', () => ({
  useAppUser: () => ({
    isReady: () => userReady
  })
}));

vi.mock('api', () => ({
  default: {
    analytic: { get: mockAnalyticGet },
    search: { analytic: { post: mockAnalyticSearchPost } }
  }
}));

import AnalyticProvider, { AnalyticContext } from './AnalyticProvider';

describe('AnalyticProvider', () => {
  const wrapper = ({ children }: any) => <AnalyticProvider>{children}</AnalyticProvider>;

  beforeEach(() => {
    userReady = true;
    mockAnalyticGet.mockReset();
    mockAnalyticSearchPost.mockReset();
  });

  it('loads analytics once the user is ready', async () => {
    mockAnalyticGet.mockResolvedValue([{ analytic_id: 'a1', name: 'Analytic One' }]);

    const { result } = renderHook(() => useContext(AnalyticContext), { wrapper });

    await waitFor(() => expect(result.current.ready).toBe(true));
    expect(result.current.analytics).toEqual([{ analytic_id: 'a1', name: 'Analytic One' }]);
    expect(mockAnalyticGet).toHaveBeenCalledTimes(1);
  });

  it('returns cached analytics and falls back to search by id', async () => {
    mockAnalyticGet.mockResolvedValue([{ analytic_id: 'a1', name: 'Analytic One' }]);
    mockAnalyticSearchPost.mockResolvedValue({ items: [{ analytic_id: 'a2', name: 'Analytic Two' }] });

    const { result } = renderHook(() => useContext(AnalyticContext), { wrapper });

    await waitFor(() => expect(result.current.ready).toBe(true));
    await expect(result.current.getAnalyticFromId('a1')).resolves.toEqual({ analytic_id: 'a1', name: 'Analytic One' });

    await act(async () => {
      await expect(result.current.getAnalyticFromId('a2')).resolves.toEqual({ analytic_id: 'a2', name: 'Analytic Two' });
    });
    expect(mockAnalyticSearchPost).toHaveBeenCalledWith({ query: 'analytic_id:a2' });
  });

  it('handles search failures gracefully', async () => {
    mockAnalyticGet.mockResolvedValue([]);
    mockAnalyticSearchPost.mockRejectedValue(new Error('boom'));
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined);

    const { result } = renderHook(() => useContext(AnalyticContext), { wrapper });
    await waitFor(() => expect(result.current.ready).toBe(true));
    await expect(result.current.getAnalyticFromId('missing')).resolves.toBeUndefined();
    expect(errorSpy).toHaveBeenCalled();
  });
});
