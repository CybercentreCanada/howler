import { BorealisProvider } from 'borealis-ui/dist/hooks/BorealisProvider';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { useContext, type PropsWithChildren } from 'react';
import { useTranslation } from 'react-i18next';
import { StorageKey } from 'utils/constants';
import { getStored } from 'utils/localStorage';

const Provider: React.FC<PropsWithChildren<{}>> = ({ children }) => {
  const apiConfig = useContext(ApiConfigContext);

  return (
    <BorealisProvider
      baseURL={location.origin + '/api/v1/borealis'}
      getToken={() => getStored(StorageKey.APP_TOKEN)}
      enabled={apiConfig.config?.configuration?.features?.borealis}
      publicIconify={false}
      customIconify={
        location.origin.includes('localhost')
          ? 'https://icons.dev.analysis.cyber.gc.ca'
          : location.origin.replace(/howler(-stg)?/, 'icons')
      }
      defaultTimeout={5}
      i18next={useTranslation('borealis')}
      chunkSize={50}
    >
      {children}
    </BorealisProvider>
  );
};

export default Provider;
