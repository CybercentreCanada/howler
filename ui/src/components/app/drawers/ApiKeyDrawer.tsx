import {
  Alert,
  AlertTitle,
  Button,
  Checkbox,
  Divider,
  FormControl,
  FormControlLabel,
  FormGroup,
  FormLabel,
  Stack,
  TextField,
  Typography
} from '@mui/material';
import { LocalizationProvider, StaticDateTimePicker } from '@mui/x-date-pickers';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import api from 'api';
import type { Privileges } from 'api/auth/apikey';
import useMyApi from 'components/hooks/useMyApi';
import useMySnackbar from 'components/hooks/useMySnackbar';
import dayjs from 'dayjs';
import type { APIConfiguration } from 'models/entities/generated/ApiType';
import type { ChangeEvent, FC } from 'react';
import { useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { ApiConfigContext } from '../providers/ApiConfigProvider';

type ApiKeyDrawerProps = {
  onCreated: (newKeyName: string, privs: string[], expiryDate: string, newKey: string) => void;
};

const ApiKeyDrawer: FC<ApiKeyDrawerProps> = ({ onCreated }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const { showInfoMessage } = useMySnackbar();
  const { config } = useContext(ApiConfigContext);

  const [keyName, setKeyName] = useState('');
  const [privs, setPrivs] = useState<Privileges[]>([]);
  const [createdKey, setCreatedKey] = useState('');
  const [expiryDate, setExpiryDate] = useState<dayjs.Dayjs>(null);

  const [amount, unit] = useMemo<[number, APIConfiguration['auth']['max_apikey_duration_unit']]>(() => {
    if (!config) {
      return [1, 'seconds'];
    }

    const { max_apikey_duration_amount: _amount, max_apikey_duration_unit: _unit } = config.configuration.auth;

    return [_amount, _unit];
  }, [config]);

  const maxDate = useMemo(() => {
    if (!amount || !unit) {
      return null;
    }

    return dayjs().add(amount, unit);
  }, [amount, unit]);

  const updatePrivs = useCallback(
    (priv: Privileges) => (ev: ChangeEvent<HTMLInputElement>) => {
      if (ev.target.checked) {
        setPrivs([...privs, priv]);
      } else {
        setPrivs(privs.filter(p => p !== priv));
      }
    },
    [privs]
  );

  const onChange = useCallback((ev: ChangeEvent<HTMLInputElement>) => {
    // Ensure the key doesn't contain any special characters
    if (!/^[a-z][a-z0-9_]*$/.test(ev.target.value) && ev.target.value !== '') {
      return;
    }
    setKeyName(ev.target.value);
  }, []);

  const onSubmit = useCallback(async () => {
    const result = await dispatchApi(api.auth.apikey.post(keyName, privs, expiryDate?.toISOString()), {
      throwError: true,
      showError: true
    });

    setCreatedKey(result.apikey);
    onCreated(result.apikey.split(':')[0], privs, expiryDate.toISOString(), result.apikey);
  }, [dispatchApi, expiryDate, keyName, onCreated, privs]);

  const onCopy = useCallback(async () => {
    await navigator.clipboard.writeText(createdKey);
    showInfoMessage(t('drawer.apikey.copied'));
  }, [createdKey, showInfoMessage, t]);

  useEffect(() => {
    setExpiryDate(maxDate);
  }, [maxDate]);

  return (
    <LocalizationProvider dateAdapter={AdapterDayjs}>
      <Stack direction="column" spacing={2} sx={{ mt: 2 }}>
        <Typography sx={{ maxWidth: '500px' }}>
          <Trans i18nKey="app.drawer.user.apikey.description" />
        </Typography>
        {amount && unit && dayjs.duration(amount, unit).asSeconds() < dayjs.duration(7, 'days').asSeconds() && (
          <Alert severity="warning" variant="outlined" sx={{ maxWidth: '500px' }}>
            <AlertTitle>{t('app.drawer.user.apikey.limit.title')}</AlertTitle>
            {t('app.drawer.user.apikey.limit.description')} ({maxDate?.format('MMM D HH:mm:ss')})
          </Alert>
        )}
        <TextField
          label={t('app.drawer.user.apikey.field.name')}
          required
          fullWidth
          value={keyName}
          onChange={onChange}
        />
        <FormControl required>
          <FormLabel component="legend">{t('app.drawer.user.apikey.permissions')}</FormLabel>
          <FormGroup sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
            <FormControlLabel control={<Checkbox onChange={updatePrivs('R')} />} label={t('apikey.read')} />
            <FormControlLabel control={<Checkbox onChange={updatePrivs('W')} />} label={t('apikey.write')} />
            <FormControlLabel
              disabled={privs.includes('E')}
              control={<Checkbox onChange={updatePrivs('I')} />}
              label={t('apikey.impersonate')}
            />
            {config.configuration.auth.allow_extended_apikeys && (
              <FormControlLabel
                disabled={privs.includes('I')}
                control={<Checkbox onChange={updatePrivs('E')} />}
                label={t('apikey.extended')}
              />
            )}
          </FormGroup>
        </FormControl>
        <FormControl required={!!maxDate}>
          <FormLabel>{t('app.drawer.user.apikey.expiry.date')}</FormLabel>
          <StaticDateTimePicker
            orientation="landscape"
            ampm={false}
            value={expiryDate}
            onChange={newValue => setExpiryDate(newValue)}
            disablePast
            maxDate={maxDate}
            maxTime={maxDate}
            sx={{ backgroundColor: 'transparent', '& > div:first-of-type': { maxWidth: '300px' } }}
          />
        </FormControl>
        <Button
          onClick={onSubmit}
          disabled={!keyName || (!privs.includes('R') && !privs.includes('W')) || (maxDate && !expiryDate)}
          variant="outlined"
        >
          <Trans i18nKey="button.create" />
        </Button>
        {createdKey && (
          <>
            <Divider orientation="horizontal" />
            <Stack direction="row" spacing={1} alignItems="stretch">
              <TextField size="small" value={createdKey} inputProps={{ readOnly: true }} fullWidth />
              <Button variant="outlined" onClick={onCopy} disabled={!createdKey}>
                <Trans i18nKey="button.copy" />
              </Button>
            </Stack>
          </>
        )}
      </Stack>
    </LocalizationProvider>
  );
};

export default ApiKeyDrawer;
