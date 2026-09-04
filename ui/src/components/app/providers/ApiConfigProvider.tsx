import type { ApiType } from 'models/entities/generated/ApiType';
import type { FC, PropsWithChildren } from 'react';
import { createContext, useMemo, useState } from 'react';
import { missingContext } from './contextUtils';

export type ApiConfigContextType = {
  config: ApiType;
  setConfig: (config: ApiType) => void;
  loaded?: boolean;
};

class PendingApiConfig implements ApiType {
  public get indexes(): ApiType['indexes'] {
    return missingContext('ApiConfigContext');
  }

  public get lookups(): ApiType['lookups'] {
    return missingContext('ApiConfigContext');
  }

  public get configuration(): ApiType['configuration'] {
    return missingContext('ApiConfigContext');
  }

  public get c12nDef(): ApiType['c12nDef'] {
    return missingContext('ApiConfigContext');
  }

  public get mapping(): ApiType['mapping'] {
    return missingContext('ApiConfigContext');
  }
}

const PENDING_API_CONFIG = new PendingApiConfig();

const DEFAULT_API_CONFIG_CONTEXT: ApiConfigContextType = {
  config: PENDING_API_CONFIG,
  setConfig: () => missingContext('ApiConfigContext'),
  loaded: false
};

export const ApiConfigContext = createContext<ApiConfigContextType>(DEFAULT_API_CONFIG_CONTEXT);

const ApiConfigProvider: FC<PropsWithChildren<{ defaultConfig?: ApiType }>> = ({ children, defaultConfig }) => {
  const [config, setConfig] = useState<ApiType | null>(defaultConfig ?? null);

  const context = useMemo<ApiConfigContextType>(
    () => ({
      config: config ?? PENDING_API_CONFIG,
      setConfig,
      loaded: config !== null
    }),
    [config, setConfig]
  );

  return <ApiConfigContext.Provider value={context}>{children}</ApiConfigContext.Provider>;
};
export default ApiConfigProvider;
