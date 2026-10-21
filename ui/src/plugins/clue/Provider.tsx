import { buildDatabase, type ClueDatabase } from '@cccsaurora/clue-ui';
import type { DatabaseConfig } from '@cccsaurora/clue-ui/database/types';
import { ClueProvider } from '@cccsaurora/clue-ui/hooks/ClueProvider';
import api from 'api';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { useCallback, useContext, useEffect, useRef, useState, type PropsWithChildren } from 'react';
import { useTranslation } from 'react-i18next';
import { StorageKey } from 'utils/constants';
import { getStored } from 'utils/localStorage';

export interface CluePluginOptions {
  baseURL?: string;
  getToken?: () => string;
  onReplicationError?: (
    error: Error & { status: number; url: string; collection: string }
  ) => boolean | Promise<boolean>;
  publicIconify?: boolean;
  customIconify?: string;
  includeContext?: boolean;
  defaultTimeout?: number;
  chunkSize?: number;
  replicate?: boolean;
  storageType?: DatabaseConfig['storageType'];
}

type ProviderProps = PropsWithChildren<{
  options?: CluePluginOptions;
}>;

const Provider: React.FC<ProviderProps> = ({ children, options = {} }) => {
  const { config } = useContext(ApiConfigContext);
  const features: { [index: string]: boolean } = config?.configuration?.features ?? {};
  const [database, setDatabase] = useState<ClueDatabase | null>(null);
  const mounted = useRef(false);
  const authRecovery = useRef<Promise<boolean> | null>(null);

  const defaultGetToken = useCallback(() => getStored<string>(StorageKey.APP_TOKEN) ?? '', []);
  const baseURL = options.baseURL ?? `${location.origin}/api/v1/clue`;
  const getToken = options.getToken ?? defaultGetToken;
  const customGetToken = options.getToken;
  const customReplicationErrorHandler = options.onReplicationError;
  const publicIconify = options.publicIconify ?? location.origin.includes('localhost');
  const customIconify = options.customIconify ?? location.origin.replace('howler', 'icons');

  useEffect(() => {
    mounted.current = true;

    return () => {
      mounted.current = false;
    };
  }, []);

  const onReplicationError = useCallback(
    async (error: Error & { status: number; url: string; collection: string }) => {
      if (!mounted.current) {
        return false;
      }

      if (customReplicationErrorHandler) {
        try {
          const shouldRetry = await customReplicationErrorHandler(error);
          return mounted.current && shouldRetry;
        } catch {
          return false;
        }
      }

      if (error.status !== 401 || customGetToken) {
        return false;
      }

      if (authRecovery.current) {
        const shouldRetry = await authRecovery.current;
        return mounted.current && shouldRetry;
      }

      try {
        const recovery = (async () => {
          try {
            const user = await api.user.whoami.get();
            const tokenAfterRecovery = getToken();
            return mounted.current && user !== undefined && !!tokenAfterRecovery;
          } catch {
            return false;
          }
        })();
        authRecovery.current = recovery;

        try {
          const shouldRetry = await recovery;
          return mounted.current && shouldRetry;
        } finally {
          if (authRecovery.current === recovery) {
            authRecovery.current = null;
          }
        }
      } catch {
        return false;
      }
    },
    [customGetToken, customReplicationErrorHandler, getToken]
  );

  useEffect(() => {
    if (!features.clue || database) {
      return;
    }

    let cancelled = false;
    const databaseConfig: DatabaseConfig & {
      onReplicationError: (
        error: Error & { status: number; url: string; collection: string }
      ) => boolean | Promise<boolean>;
    } = {
      storageType: options.storageType ?? 'memory',
      replicate: !!options.replicate,
      baseURL,
      getToken,
      onReplicationError
    };

    void buildDatabase(databaseConfig).then(database => {
      if (!cancelled) {
        setDatabase(database);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [baseURL, features.clue, getToken, onReplicationError, options.storageType, options.replicate, database]);

  return (
    <ClueProvider
      baseURL={baseURL}
      getToken={getToken}
      enabled={features.clue}
      publicIconify={publicIconify}
      customIconify={customIconify}
      defaultTimeout={options.defaultTimeout ?? 5}
      i18next={useTranslation('clue') as any}
      chunkSize={options.chunkSize ?? 50}
      database={database}
      includeContext={options.includeContext}
    >
      {children}
    </ClueProvider>
  );
};

export default Provider;
