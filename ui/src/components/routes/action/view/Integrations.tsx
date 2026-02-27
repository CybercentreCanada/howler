import { Stack, Tab, Tabs } from '@mui/material';
import PageCenter from 'commons/components/pages/PageCenter';
import Markdown from 'components/elements/display/Markdown';
import { isEmpty } from 'lodash-es';
import howlerPluginStore from 'plugins/store';
import type { FC } from 'react';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { usePluginStore } from 'react-pluggable';
import { useSearchParams } from 'react-router-dom';
import { default as INTEGRATIONS_EN, default as INTEGRATIONS_FR } from './markdown/integrations.en.md';

const Integrations: FC = () => {
  const { t } = useTranslation();
  const { i18n } = useTranslation();
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

  const md = useMemo(() => (i18n.language === 'en' ? INTEGRATIONS_EN : INTEGRATIONS_FR), [i18n.language]);

  useEffect(() => {
    searchParams.set('tab', tab);
    setSearchParams(searchParams);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  const tabData = useMemo(() => {
    if (!tab) {
      return null;
    }

    return pluginIntegrations[tab]();
  }, [pluginIntegrations, tab]);

  return (
    <PageCenter maxWidth="1500px" textAlign="left" height="100%">
      <Stack spacing={1}>
        {!isEmpty(pluginIntegrations) && (
          <Tabs value={tab} onChange={(_, _tab) => setTab(_tab)}>
            {Object.keys(pluginIntegrations).map(integration => (
              <Tab key={integration} label={t(`route.integrations.${integration}`)} value={integration} />
            ))}
          </Tabs>
        )}
        {tabData ?? <Markdown md={md} />}
      </Stack>
    </PageCenter>
  );
};

export default Integrations;
