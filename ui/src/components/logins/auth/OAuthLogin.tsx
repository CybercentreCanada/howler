import { Button, CircularProgress, Stack } from '@mui/material';
import api from 'api';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import { useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';
import { StorageKey } from 'utils/constants';
import useLogin from '../hooks/useLogin';

type OAuthLoginProps = {
  providers: string[];
};

const OAuthLogin: FC<OAuthLoginProps> = ({ providers }) => {
  const [searchParams] = useSearchParams();
  const { t } = useTranslation();
  const { doOAuth } = useLogin();
  const [buttonLoading, setButtonLoading] = useState(false);

  const setNonce = useMyLocalStorageItem(StorageKey.LOGIN_NONCE)[1];

  useEffect(() => {
    if (searchParams.get('code')) {
      setButtonLoading(true);
      doOAuth().finally(() => setButtonLoading(false));
    }
  }, [doOAuth, searchParams]);

  const nonce = useMemo(() => Math.pow(Date.now(), 1 + Math.random()).toString(16), []);

  return (
    <Stack spacing={1}>
      {providers.map(item => (
        <Button
          fullWidth
          key={item}
          variant="contained"
          color="primary"
          disabled={buttonLoading}
          href={api.auth.login.uri(new URLSearchParams({ oauth_provider: item, nonce }))}
          onClick={() => setNonce(nonce)}
          startIcon={buttonLoading && <CircularProgress size={24} />}
        >{`${t('route.login.button.oauth')} ${item.replace(/_/g, ' ')}`}</Button>
      ))}
    </Stack>
  );
};

export default OAuthLogin;
