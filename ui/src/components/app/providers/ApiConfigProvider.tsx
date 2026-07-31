import type { ApiType } from 'models/entities/generated/ApiType';
import type { FC, PropsWithChildren } from 'react';
import { createContext, useMemo, useState } from 'react';

export type ApiConfigContextType = {
  config: ApiType;
  setConfig: (config: ApiType) => void;
};

export const ApiConfigContext = createContext<ApiConfigContextType>(null as any);

const ApiConfigProvider: FC<PropsWithChildren<{ defaultConfig?: ApiType }>> = ({
  children,
  defaultConfig = {
    indexes: null as any,
    lookups: null as any,
    configuration: null as any,
    c12nDef: null as any,
    mapping: null as any
  }
}) => {
  const [config, setConfig] = useState<ApiType>(defaultConfig);

  const context = useMemo(
    () => ({
      config,
      setConfig
    }),
    [config, setConfig]
  );

  return <ApiConfigContext.Provider value={context}>{children}</ApiConfigContext.Provider>;
};
export default ApiConfigProvider;
