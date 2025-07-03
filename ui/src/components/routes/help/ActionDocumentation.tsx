import { Box, Stack, Tab, Typography, useMediaQuery, useTheme } from '@mui/material';
import PageCenter from 'commons/components/pages/PageCenter';
import { useScrollRestoration } from 'components/hooks/useScrollRestoration';
import howlerPluginStore from 'plugins/store';
import type { FC } from 'react';
import React, { useCallback, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { usePluginStore } from 'react-pluggable';
import { useSearchParams } from 'react-router-dom';
import ActionIntroductionDocumentation from './ActionIntroductionDocumentation';
import HelpTabs from './components/HelpTabs';

export interface PluginDocumentation {
  id: string;
  i18nKey: string;
  component: () => React.ReactNode;
}

const ActionDocumentation: FC = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  const pluginStore = usePluginStore();

  useScrollRestoration();

  const useHorizontal = useMediaQuery(theme.breakpoints.down(1700));

  const [searchParams, setSearchParams] = useSearchParams();
  const [tab, setTab] = useState(searchParams.get('tab') ?? 'introduction');

  const onChange = useCallback(
    (_tab: string) => {
      setTab(_tab);
      searchParams.set('tab', _tab);
      setSearchParams(new URLSearchParams(searchParams));
    },
    [searchParams, setSearchParams]
  );

  const pluginDocumentation = useMemo(
    () =>
      howlerPluginStore.operations.map(operation =>
        pluginStore.executeFunction(`operation.${operation}.documentation`)
      ),
    [pluginStore]
  );

  return (
    <PageCenter margin={4} width="100%" maxWidth="1750px" textAlign="left">
      <Stack sx={{ flexDirection: useHorizontal ? 'column' : 'row', '& h1': { mt: 0 } }}>
        <HelpTabs value={tab}>
          <Tab
            label={<Typography variant="caption">{t('help.actions.introduction')}</Typography>}
            value="introduction"
            onClick={() => onChange('introduction')}
          />
          {pluginDocumentation.map(entry => (
            <Tab
              key={entry.id}
              label={<Typography variant="caption">{t(entry.i18nKey)}</Typography>}
              value={entry.id}
              onClick={() => onChange(entry.id)}
            />
          ))}
        </HelpTabs>
        <Box>
          {{
            introduction: () => <ActionIntroductionDocumentation />,
            ...Object.fromEntries(pluginDocumentation.map(entry => [entry.id, entry.component]))
          }[tab]()}
        </Box>
      </Stack>
    </PageCenter>
  );
};

export default ActionDocumentation;
