import { Button, Stack, TextField } from '@mui/material';
import type { FormEvent } from 'react';
import { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import useLogin from '../hooks/useLogin';

const UserPassLogin = () => {
  const { t } = useTranslation();
  const { doLogin } = useLogin();
  const [loading, setLoading] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const onSubmit = useCallback(
    async (event: FormEvent) => {
      // Not preventDefault here was causing this warning:
      // Form submission canceled because the form is not connected
      // The warning seems to go away is not storing user in state.
      event.preventDefault();
      event.stopPropagation();

      if (!loading) {
        setLoading(true);
        await doLogin({ user: username, password });
        setLoading(false);
      }
    },
    [loading, doLogin, username, password]
  );

  return (
    <form onSubmit={onSubmit}>
      <Stack spacing={1}>
        <TextField
          variant="outlined"
          size="small"
          label={t('page.login.username')}
          disabled={loading}
          onChange={event => setUsername(event.target.value)}
        />
        <TextField
          variant="outlined"
          size="small"
          type="password"
          label={t('page.login.password')}
          disabled={loading}
          onChange={event => setPassword(event.target.value)}
        />
        <Button type="submit" variant="contained" color="primary" disabled={loading}>
          {t('page.login.button')}
        </Button>
      </Stack>
    </form>
  );
};

export default UserPassLogin;
