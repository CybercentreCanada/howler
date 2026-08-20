import {
  AddCircle,
  CalendarMonth,
  Dashboard,
  Dataset,
  Description,
  Folder,
  Link as LinkIcon,
  People,
  Refresh,
  Rule,
  Search,
  UnfoldLess
} from '@mui/icons-material';
import { Box, Chip, Paper, Stack, Tab, Typography, useMediaQuery, useTheme } from '@mui/material';
import PageCenter from 'commons/components/pages/PageCenter';
import Markdown from 'components/elements/display/Markdown';
import { useScrollRestoration } from 'components/hooks/useScrollRestoration';
import type { FC } from 'react';
import { useCallback, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';
import HelpTabs from './components/HelpTabs';
import FOLDERS_EN from './markdown/en/casesFolders.md';
import ITEMS_EN from './markdown/en/casesItems.md';
import INVESTIGATION_EN from './markdown/en/casesInvestigation.md';
import OVERVIEW_EN from './markdown/en/casesOverview.md';
import RECORDS_EN from './markdown/en/casesRecords.md';
import RULES_EN from './markdown/en/casesRules.md';
import SIDEBAR_EN from './markdown/en/casesSidebar.md';
import SUMMARY_EN from './markdown/en/casesSummary.md';
import FOLDERS_FR from './markdown/fr/casesFolders.md';
import ITEMS_FR from './markdown/fr/casesItems.md';
import INVESTIGATION_FR from './markdown/fr/casesInvestigation.md';
import OVERVIEW_FR from './markdown/fr/casesOverview.md';
import RECORDS_FR from './markdown/fr/casesRecords.md';
import RULES_FR from './markdown/fr/casesRules.md';
import SIDEBAR_FR from './markdown/fr/casesSidebar.md';
import SUMMARY_FR from './markdown/fr/casesSummary.md';

const CaseDocumentation: FC = () => {
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

  const sections = ['overview', 'sidebar', 'summary', 'folders', 'records', 'items', 'investigation', 'rules'] as const;
  const documentation = useMemo(
    () =>
      i18n.language === 'en'
        ? {
            overview: OVERVIEW_EN,
            sidebar: SIDEBAR_EN,
            summary: SUMMARY_EN,
            folders: FOLDERS_EN,
            records: RECORDS_EN,
            items: ITEMS_EN,
            investigation: INVESTIGATION_EN,
            rules: RULES_EN
          }
        : {
            overview: OVERVIEW_FR,
            sidebar: SIDEBAR_FR,
            summary: SUMMARY_FR,
            folders: FOLDERS_FR,
            records: RECORDS_FR,
            items: ITEMS_FR,
            investigation: INVESTIGATION_FR,
            rules: RULES_FR
          },
    [i18n.language]
  );
  const navigationItems = [
    { Icon: Dashboard, label: t('page.cases.dashboard') },
    { Icon: Search, label: t('page.cases.search') },
    { Icon: Dataset, label: t('page.cases.observables') },
    { Icon: CalendarMonth, label: t('page.cases.timeline') },
    { Icon: Rule, label: t('page.cases.rules') }
  ];

  const documentationComponents = {
    case_navigation: (
      <Paper variant="outlined" sx={{ p: 1, maxWidth: 350 }}>
        <Stack spacing={0.5}>
          {navigationItems.map(({ Icon, label }) => (
            <Stack key={label} direction="row" spacing={1} alignItems="center">
              <Icon fontSize="small" />
              <Typography variant="body2">{label}</Typography>
            </Stack>
          ))}
        </Stack>
      </Paper>
    ),
    case_controls: (
      <Stack direction="row" spacing={1}>
        <Chip icon={<Description />} label={t('page.cases.sidebar.add_item')} />
        <Chip icon={<Folder />} label={t('page.cases.sidebar.add_folder')} />
        <Chip icon={<Refresh />} label={t('page.cases.sidebar.refresh')} />
        <Chip icon={<UnfoldLess />} label={t('page.cases.sidebar.collapse_all')} />
      </Stack>
    ),
    case_details: (
      <Paper variant="outlined" sx={{ p: 1, maxWidth: 350 }}>
        <Stack spacing={1}>
          <Stack direction="row" spacing={0.5} flexWrap="wrap">
            <Chip size="small" label={t('page.cases.status.open')} />
            <Chip size="small" color="warning" label={t('page.cases.status.in-progress')} />
            <Chip size="small" color="success" label={t('page.cases.status.resolved')} />
          </Stack>
          <Stack direction="row" spacing={1} alignItems="center">
            <People fontSize="small" />
            <Typography variant="body2">{t('page.cases.detail.participants')}</Typography>
          </Stack>
        </Stack>
      </Paper>
    ),
    case_dashboard: (
      <Paper variant="outlined" sx={{ p: 2, maxWidth: 600 }}>
        <Typography variant="h6">{t('modal.cases.create_case.title')}</Typography>
        <Typography variant="body2" color="text.secondary">
          {t('modal.cases.create_case.summary')}
        </Typography>
        <Typography variant="body2" sx={{ mt: 2 }}>
          {t('modal.cases.create_case.overview')}
        </Typography>
      </Paper>
    ),
    folder_tree: (
      <Paper variant="outlined" sx={{ p: 1, maxWidth: 350 }}>
        <Stack spacing={0.5}>
          <Stack direction="row" spacing={1} alignItems="center">
            <Folder fontSize="small" />
            <Typography variant="body2">{t('help.cases.example.investigation')}</Typography>
          </Stack>
          <Stack direction="row" spacing={1} alignItems="center" pl={3}>
            <Folder fontSize="small" />
            <Typography variant="body2">{t('help.cases.example.evidence')}</Typography>
          </Stack>
          <Stack direction="row" spacing={1} alignItems="center" pl={6}>
            <Description fontSize="small" />
            <Typography variant="body2">{t('help.cases.example.analyst_notes')}</Typography>
          </Stack>
        </Stack>
      </Paper>
    ),
    add_records: (
      <Paper variant="outlined" sx={{ p: 1, maxWidth: 500 }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <AddCircle color="primary" />
          <Typography variant="body2">{t('modal.cases.add_to_case')}</Typography>
        </Stack>
      </Paper>
    ),
    case_tasks: (
      <Paper variant="outlined" sx={{ p: 1, maxWidth: 500 }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <AddCircle color="primary" />
          <Typography variant="body2">{t('page.cases.dashboard.tasks.add')}</Typography>
          <Chip size="small" label={t('page.cases.dashboard.tasks.child_cases')} />
        </Stack>
      </Paper>
    ),
    investigation_views: (
      <Paper variant="outlined" sx={{ p: 1, maxWidth: 400 }}>
        <Stack direction="row" spacing={2}>
          {[
            { Icon: Search, label: t('page.cases.search') },
            { Icon: Dataset, label: t('page.cases.observables') },
            { Icon: CalendarMonth, label: t('page.cases.timeline') }
          ].map(({ Icon, label }) => (
            <Stack key={label} alignItems="center" spacing={0.5}>
              <Icon fontSize="small" />
              <Typography variant="caption">{label}</Typography>
            </Stack>
          ))}
        </Stack>
      </Paper>
    ),
    correlation_rule: (
      <Paper variant="outlined" sx={{ p: 1, maxWidth: 600 }}>
        <Stack spacing={0.5}>
          <Typography variant="caption">{t('page.cases.rules.query')}</Typography>
          <Typography variant="body2" fontFamily="monospace">
            howler.analytic:Suspicious*
          </Typography>
          <Typography variant="caption">{t('page.cases.rules.destination')}</Typography>
          <Typography variant="body2" fontFamily="monospace">
            alerts/{'{{howler.analytic}}'}
          </Typography>
        </Stack>
      </Paper>
    ),
    case_item_types: (
      <Stack direction="row" spacing={1} flexWrap="wrap">
        <Chip icon={<Description />} label={t('modal.cases.add_item.type.markdown')} />
        <Chip icon={<LinkIcon />} label={t('modal.cases.add_item.type.link')} />
        <Chip icon={<Folder />} label={t('page.cases.sidebar.add_folder')} />
      </Stack>
    )
  };

  return (
    <PageCenter margin={4} width="100%" maxWidth="1750px" textAlign="left">
      <Stack sx={{ flexDirection: useHorizontal ? 'column' : 'row', '& h1': { mt: 0 } }}>
        <HelpTabs value={tab}>
          {sections.map(section => (
            <Tab
              key={section}
              label={<Typography variant="caption">{t(`help.cases.${section}.title`)}</Typography>}
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

export default CaseDocumentation;
