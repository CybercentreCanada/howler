import { ClueProvider } from '@cccsaurora/clue-ui/hooks/ClueProvider';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import has from 'lodash-es/has';
import { useContext, type PropsWithChildren } from 'react';
import { useTranslation } from 'react-i18next';
import { StorageKey } from 'utils/constants';
import { getStored } from 'utils/localStorage';

const Provider: React.FC<PropsWithChildren<{}>> = ({ children }) => {
  const { config } = useContext(ApiConfigContext);

  const features: { [index: string]: boolean } = config.configuration?.features ?? {};

  return (
    <ClueProvider
      baseURL={location.origin + (has(features, 'clue') ? '/api/v1/clue' : '/api/v1/borealis')}
      getToken={() => getStored(StorageKey.APP_TOKEN)}
      enabled={features.clue || features.borealis}
      publicIconify={false}
      customIconify={
        location.origin.includes('localhost')
          ? 'https://icons.dev.analysis.cyber.gc.ca'
          : location.origin.replace(/howler(-stg)?/, 'icons')
      }
      defaultTimeout={5}
      i18next={useTranslation('clue')}
      chunkSize={50}
    >
      {children}
    </ClueProvider>
  );
};

export default Provider;
