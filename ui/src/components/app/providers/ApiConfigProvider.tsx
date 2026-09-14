import { isEmpty } from 'lodash-es';
import type { ApiType } from 'models/entities/generated/ApiType';
import type { FC, PropsWithChildren } from 'react';
import { createContext, useMemo, useState } from 'react';
import { missingContext } from './contextUtils';

export type ApiConfigContextType = {
  config: Partial<ApiType>;
  setConfig: (config: ApiType) => void;
  loaded: boolean;
};

const DEFAULT_API_CONFIG_CONTEXT: ApiConfigContextType = {
  config: {},
  setConfig: () => missingContext('ApiConfigContext'),
  loaded: false
};

export const ApiConfigContext = createContext<ApiConfigContextType>(DEFAULT_API_CONFIG_CONTEXT);

const ApiConfigProvider: FC<PropsWithChildren<{ defaultConfig?: ApiType }>> = ({ children, defaultConfig }) => {
  const [config, setConfig] = useState<Partial<ApiType>>(defaultConfig ?? {});

  const context = useMemo<ApiConfigContextType>(
    () => ({
      config,
      setConfig,
      loaded: !isEmpty(config)
    }),
    [config, setConfig]
  );

  return <ApiConfigContext.Provider value={context}>{children}</ApiConfigContext.Provider>;
};
export default ApiConfigProvider;
