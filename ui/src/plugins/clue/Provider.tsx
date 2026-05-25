import { ClueProvider } from '@cccsaurora/clue-ui/hooks/ClueProvider';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { useContext, type PropsWithChildren } from 'react';
import { useTranslation } from 'react-i18next';
import { StorageKey } from 'utils/constants';
import { getStored } from 'utils/localStorage';

const Provider: React.FC<PropsWithChildren<{}>> = ({ children }) => {
  const { config } = useContext(ApiConfigContext);

  const features: { [index: string]: boolean } = config.configuration?.features ?? {};

  return (
    <ClueProvider
      baseURL={location.origin + '/api/v1/clue'}
      getToken={() => getStored(StorageKey.APP_TOKEN)}
      enabled={features.clue}
      publicIconify={location.origin.includes('localhost')}
      customIconify={location.origin.replace(/howler(-stg)?/, 'icons')}
      defaultTimeout={5}
      i18next={useTranslation('clue')}
      chunkSize={50}
    >
      {children}
    </ClueProvider>
  );
};

export default Provider;
