import { Stack, Tab, Tabs } from '@mui/material';
import PageCenter from 'commons/components/pages/PageCenter';
import howlerPluginStore from 'plugins/store';
import type { FC } from 'react';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { usePluginStore } from 'react-pluggable';
import { useSearchParams } from 'react-router-dom';

const Integrations: FC = () => {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const pluginStore = usePluginStore();

  const pluginIntegrations = useMemo(
    () =>
      Object.fromEntries(
        howlerPluginStore.plugins.flatMap(plugin => pluginStore.executeFunction(`${plugin}.integrations`))
      ),
    [pluginStore]
  );

  const [tab, setTab] = useState(Object.keys(pluginIntegrations)[0] ?? '');

  useEffect(() => {
    searchParams.set('tab', tab);
    setSearchParams(searchParams);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  const tabData = useMemo(() => {
    return pluginIntegrations[tab]();
  }, [pluginIntegrations, tab]);

  return (
    <PageCenter maxWidth="1500px" textAlign="left" height="100%">
      <Stack spacing={1}>
        <Tabs value={tab} onChange={(_, _tab) => setTab(_tab)}>
          {Object.keys(pluginIntegrations).map(integration => (
            <Tab key={integration} label={t(`route.integrations.${integration}`)} value={integration} />
          ))}
        </Tabs>
        {tabData}
      </Stack>
    </PageCenter>
  );
};

export default Integrations;
