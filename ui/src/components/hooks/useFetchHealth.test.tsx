import { renderHook, waitFor } from '@testing-library/react';
import { expect, vi } from 'vitest';
import useFetchHealth from '../hooks/useFetchHealth';

vi.mock('api');

afterEach(() => {
  vi.clearAllMocks();
  vi.clearAllTimers();
});



beforeEach(() => {
    // Here we tell Vitest to mock fetch on the `window` object.
    global.fetch = vi.fn(() =>
      Promise.reject(),
    );
});

describe('test initial state of hook', () => {
  it('should return the initial values for data and loading on rejected promise', async () => {
    const { result } = renderHook(() => useFetchHealth({ pollingRateMS: 0 }));
    await waitFor(() => {
      const { healthStatus, loading } = result.current;
      expect(healthStatus).toEqual([]);
      expect(loading).toBe(false);
    });
  });
});

describe('test when data is successfully fetched', () => {
  const mockedPluginHealths = [
    { name: 'htestplugin', healthy: true, importance: "critical" },
    { name: 'atestplugin', healthy: false, importance: "optional" },
    { name: 'ztestplugin', healthy: true, importance: "optional" }
  ];

  beforeEach(() => {
    global.fetch = vi.fn(() =>
      Promise.resolve(new Response(JSON.stringify(mockedPluginHealths))),
    );
  });

  it('should return the data fetched, sorted and set loading to false', async () => {
    const { result } = renderHook(() => useFetchHealth({ pollingRateMS: 0 }));

    await waitFor(() => {
      expect(result.current.healthStatus).toEqual([
        {
          name: 'atestplugin',
          healthy: false,
          importance: "optional"
        },
        {
          name: 'htestplugin',
          healthy: true,
          importance: "critical"
        },
        {
          name: 'ztestplugin',
          healthy: true,
          importance: "optional"
        }
      ]);
      expect(result.current.loading).toBe(false);
    });
  });
});
