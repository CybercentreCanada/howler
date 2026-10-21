import { act, render, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

type ClueProviderProps = {
  baseURL?: string;
  chunkSize?: number;
  customIconify?: string;
  database?: unknown;
  defaultTimeout?: number;
  enabled?: boolean;
  getToken?: () => string;
  includeContext?: boolean;
  publicIconify?: boolean;
};

const mocks = vi.hoisted(() => ({
  buildDatabase: vi.fn(),
  clueProviderProps: undefined as ClueProviderProps | undefined,
  whoamiGet: vi.fn(),
  token: 'stored-token' as string | null
}));

vi.mock('@cccsaurora/clue-ui', () => ({
  buildDatabase: mocks.buildDatabase
}));

vi.mock('api', () => ({
  default: { user: { whoami: { get: mocks.whoamiGet } } }
}));

vi.mock('@cccsaurora/clue-ui/hooks/ClueProvider', () => ({
  ClueProvider: ({ children, ...props }: { children?: ReactNode }) => {
    mocks.clueProviderProps = props;
    return <>{children}</>;
  }
}));

vi.mock('components/app/providers/ApiConfigProvider', async () => {
  const { createContext } = await import('react');
  return { ApiConfigContext: createContext({ config: {} }) };
});

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ i18n: { language: 'en' } })
}));

vi.mock('utils/constants', () => ({
  StorageKey: { APP_TOKEN: 'app_token' }
}));

vi.mock('utils/localStorage', () => ({
  getStored: () => mocks.token
}));

import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import Provider, { type CluePluginOptions } from './Provider';

const getProviderProps = () => {
  if (!mocks.clueProviderProps) {
    throw new Error('ClueProvider was not rendered');
  }

  return mocks.clueProviderProps;
};

const renderProvider = (config: object, options?: CluePluginOptions) =>
  render(
    <ApiConfigContext.Provider value={{ config: config as never, setConfig: vi.fn(), loaded: true }}>
      <Provider options={options}>content</Provider>
    </ApiConfigContext.Provider>
  );

type ClueReplicationError = Error & { status: number; url: string; collection: string };

const getReplicationErrorHandler = () => {
  const databaseConfig = mocks.buildDatabase.mock.calls[0]?.[0] as
    | { onReplicationError?: (error: ClueReplicationError) => Promise<boolean> }
    | undefined;

  if (!databaseConfig?.onReplicationError) {
    throw new Error('Replication error handler was not configured');
  }

  return databaseConfig.onReplicationError;
};

const makeReplicationError = (status: number): ClueReplicationError =>
  Object.assign(new Error('replication failed'), {
    status,
    url: '/api/v1/clue/stream',
    collection: 'alerts'
  });

describe('Clue Provider', () => {
  beforeEach(() => {
    mocks.buildDatabase.mockReset();
    mocks.whoamiGet.mockReset();
    mocks.whoamiGet.mockImplementation(async () => ({}));
    mocks.clueProviderProps = undefined;
    mocks.token = 'stored-token';
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('does not start replication while Clue is disabled and returns an empty absent token', () => {
    mocks.token = null;

    renderProvider({ configuration: { features: { clue: false } } });

    expect(mocks.buildDatabase).not.toHaveBeenCalled();
    expect(getProviderProps().enabled).toBe(false);
    expect(getProviderProps().database).toBeNull();
    expect(getProviderProps().getToken?.()).toBe('');
  });

  it('returns the current stored application token by default', () => {
    renderProvider({ configuration: { features: { clue: false } } });

    expect(getProviderProps().getToken?.()).toBe('stored-token');
  });

  it('builds a configured database and passes supplied deployment options', async () => {
    const database = { name: 'replicated' };
    const getToken = vi.fn(() => 'custom-token');
    mocks.buildDatabase.mockResolvedValue(database);

    renderProvider(
      { configuration: { features: { clue: true } } },
      {
        baseURL: 'https://howler.example/api/v1/clue',
        getToken,
        publicIconify: false,
        customIconify: 'https://icons.example',
        includeContext: true,
        defaultTimeout: 7,
        chunkSize: 25,
        replicate: true,
        storageType: 'memory'
      }
    );

    await waitFor(() => {
      expect(mocks.buildDatabase).toHaveBeenCalledWith({
        storageType: 'memory',
        replicate: true,
        baseURL: 'https://howler.example/api/v1/clue',
        getToken,
        onReplicationError: expect.any(Function)
      });
      expect(getProviderProps().database).toBe(database);
    });

    expect(getProviderProps()).toMatchObject({
      baseURL: 'https://howler.example/api/v1/clue',
      database,
      enabled: true,
      publicIconify: false,
      customIconify: 'https://icons.example',
      includeContext: true,
      defaultTimeout: 7,
      chunkSize: 25
    });
  });

  it('uses non-replicated in-memory storage by default', async () => {
    mocks.buildDatabase.mockResolvedValue({ name: 'local' });

    renderProvider({ configuration: { features: { clue: true } } });

    await waitFor(() => {
      expect(mocks.buildDatabase).toHaveBeenCalledWith({
        storageType: 'memory',
        replicate: false,
        baseURL: `${location.origin}/api/v1/clue`,
        getToken: expect.any(Function),
        onReplicationError: expect.any(Function)
      });
    });
  });

  it('accepts a successful session check with a nonempty already-refreshed token', async () => {
    mocks.buildDatabase.mockResolvedValue({ name: 'replicated' });
    mocks.token = 'already-refreshed-token';

    renderProvider({ configuration: { features: { clue: true } } }, { replicate: true });
    await waitFor(() => expect(mocks.buildDatabase).toHaveBeenCalled());

    await expect(getReplicationErrorHandler()(makeReplicationError(401))).resolves.toBe(true);
    expect(mocks.whoamiGet).toHaveBeenCalledOnce();
  });

  it('does not refresh non-401 errors and refuses failed or empty session refreshes', async () => {
    mocks.buildDatabase.mockResolvedValue({ name: 'replicated' });
    renderProvider({ configuration: { features: { clue: true } } }, { replicate: true });
    await waitFor(() => expect(mocks.buildDatabase).toHaveBeenCalled());

    const onReplicationError = getReplicationErrorHandler();
    await expect(onReplicationError(makeReplicationError(403))).resolves.toBe(false);
    expect(mocks.whoamiGet).not.toHaveBeenCalled();

    mocks.whoamiGet.mockRejectedValueOnce(new Error('refresh failed'));
    await expect(onReplicationError(makeReplicationError(401))).resolves.toBe(false);
    mocks.whoamiGet.mockResolvedValueOnce(undefined);
    await expect(onReplicationError(makeReplicationError(401))).resolves.toBe(false);
    mocks.whoamiGet.mockResolvedValueOnce({});
    mocks.token = null;
    await expect(onReplicationError(makeReplicationError(401))).resolves.toBe(false);
    expect(mocks.whoamiGet).toHaveBeenCalledTimes(3);
  });

  it('coalesces concurrent replication auth recoveries', async () => {
    let resolveRefresh: ((value: { username: string }) => void) | undefined;
    mocks.whoamiGet.mockReturnValue(
      new Promise<{ username: string }>(resolve => {
        resolveRefresh = resolve;
      })
    );
    mocks.buildDatabase.mockResolvedValue({ name: 'replicated' });

    renderProvider({ configuration: { features: { clue: true } } }, { replicate: true });
    await waitFor(() => expect(mocks.buildDatabase).toHaveBeenCalled());

    const onReplicationError = getReplicationErrorHandler();
    const firstRecovery = onReplicationError(makeReplicationError(401));
    const secondRecovery = onReplicationError(makeReplicationError(401));

    await waitFor(() => expect(mocks.whoamiGet).toHaveBeenCalledOnce());
    mocks.token = 'refreshed-token';
    resolveRefresh?.({ username: 'user' });

    await expect(Promise.all([firstRecovery, secondRecovery])).resolves.toEqual([true, true]);
    expect(mocks.whoamiGet).toHaveBeenCalledOnce();
  });

  it('refuses pending default and coalesced recoveries that settle after unmount', async () => {
    let resolveRefresh: ((value: { username: string }) => void) | undefined;
    mocks.whoamiGet.mockReturnValue(
      new Promise<{ username: string }>(resolve => {
        resolveRefresh = resolve;
      })
    );
    mocks.buildDatabase.mockResolvedValue({ name: 'replicated' });

    const { unmount } = renderProvider({ configuration: { features: { clue: true } } }, { replicate: true });
    await waitFor(() => expect(mocks.buildDatabase).toHaveBeenCalled());

    const onReplicationError = getReplicationErrorHandler();
    const firstRecovery = onReplicationError(makeReplicationError(401));
    const coalescedRecovery = onReplicationError(makeReplicationError(401));
    await waitFor(() => expect(mocks.whoamiGet).toHaveBeenCalledOnce());

    await act(async () => {
      resolveRefresh?.({ username: 'user' });
      await Promise.resolve();
      unmount();
    });

    await expect(Promise.all([firstRecovery, coalescedRecovery])).resolves.toEqual([false, false]);
  });

  it('preserves custom token getters and does not refresh them without an override', async () => {
    mocks.buildDatabase.mockResolvedValue({ name: 'replicated' });
    const getToken = vi.fn(() => 'custom-token');

    renderProvider({ configuration: { features: { clue: true } } }, { replicate: true, getToken });
    await waitFor(() => expect(mocks.buildDatabase).toHaveBeenCalled());

    expect(mocks.buildDatabase.mock.calls[0][0]).toMatchObject({ getToken });
    expect(getProviderProps().getToken).toBe(getToken);
    await expect(getReplicationErrorHandler()(makeReplicationError(401))).resolves.toBe(false);
    expect(mocks.whoamiGet).not.toHaveBeenCalled();
  });

  it('uses the custom replication error handler for custom token deployments', async () => {
    mocks.buildDatabase.mockResolvedValue({ name: 'replicated' });
    const getToken = vi.fn(() => 'custom-token');
    const onReplicationError = vi.fn(async () => true);

    renderProvider({ configuration: { features: { clue: true } } }, { replicate: true, getToken, onReplicationError });
    await waitFor(() => expect(mocks.buildDatabase).toHaveBeenCalled());

    const error = makeReplicationError(401);
    await expect(getReplicationErrorHandler()(error)).resolves.toBe(true);
    expect(mocks.buildDatabase.mock.calls[0][0]).toMatchObject({ getToken });
    expect(mocks.buildDatabase.mock.calls[0][0].onReplicationError).toEqual(expect.any(Function));
    expect(onReplicationError).toHaveBeenCalledWith(error);
    expect(mocks.whoamiGet).not.toHaveBeenCalled();
  });

  it('refuses a custom recovery that settles after unmount', async () => {
    let resolveCustomRecovery: ((shouldRetry: boolean) => void) | undefined;
    const onReplicationError = vi.fn(
      () =>
        new Promise<boolean>(resolve => {
          resolveCustomRecovery = resolve;
        })
    );
    mocks.buildDatabase.mockResolvedValue({ name: 'replicated' });

    const { unmount } = renderProvider(
      { configuration: { features: { clue: true } } },
      { replicate: true, getToken: () => 'custom-token', onReplicationError }
    );
    await waitFor(() => expect(mocks.buildDatabase).toHaveBeenCalled());

    const pendingRecovery = getReplicationErrorHandler()(makeReplicationError(401));
    await waitFor(() => expect(onReplicationError).toHaveBeenCalledOnce());

    act(() => unmount());
    resolveCustomRecovery?.(true);

    await expect(pendingRecovery).resolves.toBe(false);
  });

  it('does not refresh after the provider unmounts', async () => {
    mocks.buildDatabase.mockResolvedValue({ name: 'replicated' });
    const { unmount } = renderProvider({ configuration: { features: { clue: true } } }, { replicate: true });
    await waitFor(() => expect(mocks.buildDatabase).toHaveBeenCalled());
    const onReplicationError = getReplicationErrorHandler();
    unmount();

    await expect(onReplicationError(makeReplicationError(401))).resolves.toBe(false);
    expect(mocks.whoamiGet).not.toHaveBeenCalled();
  });

  it('ignores a database that resolves after the provider unmounts', async () => {
    let resolveDatabase: (database: object) => void = () => {};
    mocks.buildDatabase.mockReturnValue(
      new Promise(resolve => {
        resolveDatabase = resolve;
      })
    );

    const { unmount } = renderProvider({ configuration: { features: { clue: true } } });
    unmount();

    await act(async () => {
      resolveDatabase({ name: 'late' });
    });

    expect(getProviderProps().database).toBeNull();
  });
});
