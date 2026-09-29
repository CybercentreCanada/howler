/// <reference types="vitest" />
import { act, renderHook, waitFor } from '@testing-library/react';
import { useContext } from 'react';
import { setupContextSelectorMock } from 'tests/mocks';
import { beforeEach, describe, expect, it, vi } from 'vitest';

setupContextSelectorMock();

const mockOverviewGet = vi.hoisted(() => vi.fn());

vi.mock('api', () => ({
  default: {
    overview: {
      get: mockOverviewGet
    }
  }
}));

import OverviewProvider, { OverviewContext } from './OverviewProvider';

describe('OverviewProvider', () => {
  const wrapper = ({ children }: any) => <OverviewProvider>{children}</OverviewProvider>;

  beforeEach(() => {
    mockOverviewGet.mockReset();
  });

  it('loads and caches overviews until forced to refresh', async () => {
    const dataset = [
      { overview_id: '1', analytic: 'a1' },
      { overview_id: '2', analytic: 'a2', detection: 'Phishing' }
    ];
    mockOverviewGet.mockResolvedValue(dataset);

    const { result } = renderHook(() => useContext(OverviewContext), { wrapper });

    await act(async () => {
      await expect(result.current.getOverviews()).resolves.toEqual(dataset);
    });
    await waitFor(() => expect(result.current.loaded).toBe(true));
    expect(mockOverviewGet).toHaveBeenCalledTimes(1);

    await act(async () => {
      await expect(result.current.getOverviews()).resolves.toEqual(dataset);
    });
    expect(mockOverviewGet).toHaveBeenCalledTimes(1);

    await act(async () => {
      await expect(result.current.getOverviews(true)).resolves.toEqual(dataset);
    });
    expect(mockOverviewGet).toHaveBeenCalledTimes(2);
  });

  it('matches the most specific overview for a hit and can refresh state', async () => {
    mockOverviewGet.mockResolvedValue([
      { overview_id: 'generic', analytic: 'analytic-1' },
      { overview_id: 'specific', analytic: 'analytic-1', detection: 'Malware' }
    ]);

    const { result } = renderHook(() => useContext(OverviewContext), { wrapper });
    await act(async () => {
      await result.current.getOverviews();
    });

    expect(
      result.current.getMatchingOverview({ howler: { analytic: 'analytic-1', detection: 'malware' } } as any)
    ).toMatchObject({ overview_id: 'specific' });
    expect(result.current.getMatchingOverview({ howler: { analytic: 'analytic-1' } } as any)).toMatchObject({
      overview_id: 'generic'
    });

    mockOverviewGet.mockResolvedValueOnce([{ overview_id: 'refreshed', analytic: 'analytic-2' }]);
    act(() => {
      result.current.refresh();
    });
    await waitFor(() => expect(mockOverviewGet).toHaveBeenCalledTimes(2));
  });
});
