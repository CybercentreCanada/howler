import { HelpCenter, OpenInNew } from '@mui/icons-material';
import {
  Button,
  Card,
  CardActions,
  CardContent,
  CardHeader,
  Divider,
  Grid,
  IconButton,
  Stack,
  Typography
} from '@mui/material';
import type { AppLeftNavGroup } from 'commons/components/app/AppConfigs';
import PageCenter from 'commons/components/pages/PageCenter';
import useMyPreferences from 'components/hooks/useMyPreferences';
import { useScrollRestoration } from 'components/hooks/useScrollRestoration';
import howlerPluginStore from 'plugins/store';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { usePluginStore } from 'react-pluggable';
import { Link } from 'react-router-dom';

const HelpDashboard = () => {
  const { t } = useTranslation(['translation', 'helpMain']);
  const { leftnav } = useMyPreferences();
  const pluginStore = usePluginStore();

  useScrollRestoration();

  const tabs = useMemo(
    () => ({
      'help.hit': ['schema', 'header', 'bundle', 'links'],
      'help.actions': ['introduction', ...howlerPluginStore.operations]
    }),
    []
  );

  const links = useMemo(
    () =>
      (
        leftnav.elements.find(el => el.type === 'group' && el.element.id === 'help')!.element as AppLeftNavGroup
      ).items.filter(_item => _item.id !== 'help.main'),
    [leftnav.elements]
  );

  return (
    <PageCenter margin={4} width="100%" maxWidth="1750px" textAlign="left">
      <Stack spacing={1}>
        <Typography variant="h3" sx={{ display: 'flex', flexDirection: 'row', alignItems: 'center' }}>
          <HelpCenter fontSize="inherit" sx={{ mr: 1 }} />
          <span>{t('page.help.title')}</span>
        </Typography>
        <Divider sx={theme => ({ marginLeft: `${theme.spacing(1)} !important` })} />
        <Grid container spacing={1} sx={{ pr: 1 }}>
          {links.map(link => (
            <Grid item xs={12} md={3} key={link.id} sx={{ display: 'flex' }}>
              <Card sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                <CardHeader
                  title={
                    <Stack
                      direction="row"
                      alignItems="center"
                      sx={{ '& svg': { fontSize: 'inherit' }, '& > span': { ml: 1 } }}
                    >
                      {link.icon}
                      <span>{t(link.i18nKey)}</span>
                      <IconButton component={Link} to={link.route} sx={{ ml: 'auto' }}>
                        <OpenInNew color="primary" fontSize="inherit" />
                      </IconButton>
                    </Stack>
                  }
                />
                <CardContent sx={{ flex: 1 }}>
                  <Typography>{t(`helpMain:${link.i18nKey}.description`)}</Typography>
                </CardContent>
                {tabs[link.id] && (
                  <CardActions>
                    {tabs[link.id].map(tab => (
                      <Button key={tab} size="small" component={Link} to={`${link.route}?tab=${tab}`}>
                        {tab}
                      </Button>
                    ))}
                  </CardActions>
                )}
              </Card>
            </Grid>
          ))}
        </Grid>
        {howlerPluginStore.plugins.map(plugin => pluginStore.executeFunction(`${plugin}.help`))}
      </Stack>
    </PageCenter>
  );
};

export default HelpDashboard;
