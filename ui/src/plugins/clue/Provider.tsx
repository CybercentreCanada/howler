import { buildDatabase, type ClueDatabase } from '@cccsaurora/clue-ui';
import type { DatabaseConfig } from '@cccsaurora/clue-ui/database/types';
import { ClueProvider } from '@cccsaurora/clue-ui/hooks/ClueProvider';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { useCallback, useContext, useEffect, useState, type PropsWithChildren } from 'react';
import { useTranslation } from 'react-i18next';
import { StorageKey } from 'utils/constants';
import { getStored } from 'utils/localStorage';

export interface CluePluginOptions {
  baseURL?: string;
  getToken?: () => string;
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
  const [database, setDatabase] = useState<ClueDatabase>();

  const defaultGetToken = useCallback(() => getStored<string>(StorageKey.APP_TOKEN) ?? '', []);
  const baseURL = options.baseURL ?? `${location.origin}/api/v1/clue`;
  const getToken = options.getToken ?? defaultGetToken;
  const publicIconify = options.publicIconify ?? location.origin.includes('localhost');
  const customIconify = options.customIconify ?? location.origin.replace('howler', 'icons');

  useEffect(() => {
    let cancelled = false;

    if (!features.clue) {
      return;
    }

    void buildDatabase({
      storageType: options.storageType ?? 'memory',
      replicate: !!options.replicate,
      baseURL,
      getToken
    }).then(database => {
      if (!cancelled) {
        setDatabase(database);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [baseURL, features.clue, getToken, options.storageType, options.replicate]);

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
