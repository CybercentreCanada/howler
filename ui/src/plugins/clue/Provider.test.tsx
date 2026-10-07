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
  token: 'stored-token' as string | null
}));

vi.mock('@cccsaurora/clue-ui', () => ({
  buildDatabase: mocks.buildDatabase
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

describe('Clue Provider', () => {
  beforeEach(() => {
    mocks.buildDatabase.mockReset();
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
    expect(getProviderProps().database).toBeUndefined();
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
        getToken
      });
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
        getToken: expect.any(Function)
      });
    });
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

    expect(getProviderProps().database).toBeUndefined();
  });
});
