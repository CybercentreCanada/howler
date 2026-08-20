import { Article, Language, Link as LinkIcon, Person, Search } from '@mui/icons-material';
import { Box, Chip, Paper, Stack, Tab, Typography, useMediaQuery, useTheme } from '@mui/material';
import PageCenter from 'commons/components/pages/PageCenter';
import Markdown from 'components/elements/display/Markdown';
import { useScrollRestoration } from 'components/hooks/useScrollRestoration';
import type { FC } from 'react';
import { useCallback, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';
import HelpTabs from './components/HelpTabs';
import LEADS_EN from './markdown/en/dossiersLeads.md';
import OVERVIEW_EN from './markdown/en/dossiersOverview.md';
import PIVOTS_EN from './markdown/en/dossiersPivots.md';
import QUERY_EN from './markdown/en/dossiersQuery.md';
import USAGE_EN from './markdown/en/dossiersUsage.md';
import LEADS_FR from './markdown/fr/dossiersLeads.md';
import OVERVIEW_FR from './markdown/fr/dossiersOverview.md';
import PIVOTS_FR from './markdown/fr/dossiersPivots.md';
import QUERY_FR from './markdown/fr/dossiersQuery.md';
import USAGE_FR from './markdown/fr/dossiersUsage.md';

const DossierDocumentation: FC = () => {
  const { i18n, t } = useTranslation();
  const theme = useTheme();
  const useHorizontal = useMediaQuery(theme.breakpoints.down(1700));
  useScrollRestoration();

  const [searchParams, setSearchParams] = useSearchParams();
  const [tab, setTab] = useState(searchParams.get('tab') ?? 'overview');

  const onChange = useCallback(
    (nextTab: string) => {
      setTab(nextTab);
      searchParams.set('tab', nextTab);
      setSearchParams(new URLSearchParams(searchParams));
    },
    [searchParams, setSearchParams]
  );

  const sections = ['overview', 'query', 'leads', 'pivots', 'usage'] as const;
  const documentation = useMemo(
    () =>
      i18n.language === 'en'
        ? {
            overview: OVERVIEW_EN,
            query: QUERY_EN,
            leads: LEADS_EN,
            pivots: PIVOTS_EN,
            usage: USAGE_EN
          }
        : {
            overview: OVERVIEW_FR,
            query: QUERY_FR,
            leads: LEADS_FR,
            pivots: PIVOTS_FR,
            usage: USAGE_FR
          },
    [i18n.language]
  );

  const documentationComponents = {
    dossier_delivery: (
      <Paper variant="outlined" sx={{ p: 1, maxWidth: 500 }}>
        <Stack spacing={1}>
          <Typography variant="subtitle2">{t('route.hits.view')}</Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap">
            <Chip icon={<Article />} label={t('route.dossiers.manager.tabs.leads')} />
            <Chip icon={<LinkIcon />} label={t('route.dossiers.manager.tabs.pivots')} />
          </Stack>
        </Stack>
      </Paper>
    ),
    dossier_scope: (
      <Stack direction="row" spacing={1} flexWrap="wrap">
        <Chip icon={<Language />} label={t('route.dossiers.manager.global')} />
        <Chip icon={<Person />} label={t('route.dossiers.manager.personal')} />
      </Stack>
    ),
    dossier_query: (
      <Paper variant="outlined" sx={{ p: 1, maxWidth: 500 }}>
        <Stack spacing={0.5}>
          <Typography variant="caption" color="text.secondary">
            {t('route.dossiers.manager.field.query')}
          </Typography>
          <Typography variant="body2" fontFamily="monospace">
            {'howler.analytic:"VPN Monitor" AND howler.status:open'}
          </Typography>
          <Chip
            size="small"
            sx={{ alignSelf: 'start', mt: 0.5 }}
            icon={<Search />}
            label={t('route.dossiers.manager.openinsearch')}
          />
        </Stack>
      </Paper>
    ),
    dossier_lead: (
      <Paper variant="outlined" sx={{ p: 1, maxWidth: 500 }}>
        <Stack spacing={0.5}>
          <Stack direction="row" spacing={1} alignItems="center">
            <Article fontSize="small" />
            <Typography variant="body2">{t('route.dossiers.manager.tabs.leads')}</Typography>
          </Stack>
          <Typography variant="caption" color="text.secondary">
            {'markdown'}
          </Typography>
        </Stack>
      </Paper>
    ),
    dossier_pivot: (
      <Paper variant="outlined" sx={{ p: 1, maxWidth: 600 }}>
        <Stack spacing={0.5}>
          <Stack direction="row" spacing={1} alignItems="center">
            <LinkIcon fontSize="small" />
            <Typography variant="body2">{t('route.dossiers.manager.tabs.pivots')}</Typography>
          </Stack>
          <Typography variant="body2" fontFamily="monospace">
            {'https://investigate.example/?host={{hostname}}'}
          </Typography>
        </Stack>
      </Paper>
    )
  };

  return (
    <PageCenter margin={4} width="100%" maxWidth="1750px" textAlign="left">
      <Stack sx={{ flexDirection: useHorizontal ? 'column' : 'row', '& h1': { mt: 0 } }}>
        <HelpTabs value={tab}>
          {sections.map(section => (
            <Tab
              key={section}
              label={<Typography variant="caption">{t(`help.dossiers.${section}.title`)}</Typography>}
              value={section}
              onClick={() => onChange(section)}
            />
          ))}
        </HelpTabs>
        <Box>{tab in documentation && <Markdown md={documentation[tab]} components={documentationComponents} />}</Box>
      </Stack>
    </PageCenter>
  );
};

export default DossierDocumentation;
