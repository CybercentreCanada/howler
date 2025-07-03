import AddIcon from '@mui/icons-material/Add';
import { Chip, Grid, IconButton, TableCell, TableRow } from '@mui/material';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import useMyLocalStorage from 'components/hooks/useMyLocalStorage';
import type { HowlerUser } from 'models/entities/HowlerUser';
import moment from 'moment';
import howlerPluginStore from 'plugins/store';
import type { FC } from 'react';
import { useContext, useMemo } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { usePluginStore } from 'react-pluggable';
import { StorageKey } from 'utils/constants';
import EditRow from '../../elements/EditRow';
import SettingsSection from './SettingsSection';

const APIKEY_LABELS = {
  R: 'apikey.read',
  W: 'apikey.write',
  E: 'apikey.extended',
  I: 'apikey.impersonate'
};

const SecuritySection: FC<{
  user: HowlerUser;
  editPassword?: (password: string) => Promise<void>;
  addApiKey?: () => void;
  removeApiKey?: (apiKey: [string, string[], string]) => Promise<void>;
  editQuota?: (quote?: string) => Promise<void>;
}> = ({ user, editPassword, addApiKey, removeApiKey, editQuota }) => {
  const { t } = useTranslation();
  const { get } = useMyLocalStorage();
  const { config } = useContext(ApiConfigContext);
  const pluginStore = usePluginStore();

  const isOAuth = useMemo(() => get<string>(StorageKey.APP_TOKEN)?.includes('.'), [get]);

  return (
    <SettingsSection title={t('page.settings.security.title')} colSpan={3}>
      {!isOAuth && editPassword && (
        <EditRow
          titleKey="page.settings.security.table.password"
          value="●●●●●●●●●●●"
          onEdit={editPassword}
          type="password"
        />
      )}
      {config?.configuration.auth.allow_apikeys && (
        <TableRow sx={{ cursor: 'pointer' }}>
          <TableCell style={{ whiteSpace: 'nowrap' }}>{t('page.settings.security.table.apikeys')}</TableCell>
          <TableCell width="100%">
            <Grid container spacing={1}>
              {user?.apikeys?.map(apiKey => (
                <Grid item key={apiKey[0]}>
                  <Chip
                    label={
                      apiKey[0].toLocaleLowerCase() +
                      (apiKey[1].length > 0
                        ? ` (${apiKey[1].map(permission => t(APIKEY_LABELS[permission])).join(', ')})`
                        : '')
                    }
                    style={{ backgroundColor: moment.utc(apiKey[2]).isBefore(moment().utc()) ? 'orange' : 'default' }}
                    onDelete={removeApiKey ? () => removeApiKey(apiKey) : null}
                  />
                </Grid>
              ))}
              {user?.apikeys?.length < 1 && (
                <Grid item>
                  <Trans i18nKey="none" />
                </Grid>
              )}
            </Grid>
          </TableCell>
          <TableCell align="right">
            {addApiKey && (
              <IconButton onClick={addApiKey}>
                <AddIcon fontSize="small" />
              </IconButton>
            )}
          </TableCell>
        </TableRow>
      )}
      <EditRow
        titleKey="page.settings.security.table.apiquota"
        descriptionKey="page.settings.security.table.apiquota.description"
        value={user?.api_quota}
        validate={value => value && /^[0-9]*$/m.test(value.toString())}
        type="number"
        onEdit={editQuota}
      />
      {howlerPluginStore.plugins.map(plugin => pluginStore.executeFunction(`${plugin}.settings`, 'security'))}
    </SettingsSection>
  );
};

export default SecuritySection;
