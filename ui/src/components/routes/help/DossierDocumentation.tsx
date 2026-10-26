import { Icon } from '@iconify/react';
import { Language, Person } from '@mui/icons-material';
import {
  Box,
  Stack,
  Tab,
  Tabs,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme
} from '@mui/material';
import { PageCenter } from '@tui/core';
import Markdown from 'components/elements/display/Markdown';
import PivotLink from 'components/elements/hit/related/pivots/PivotLink';
import { useScrollRestoration } from 'components/hooks/useScrollRestoration';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { Lead } from 'models/entities/generated/Lead';
import type { Pivot } from 'models/entities/generated/Pivot';
import { useCallback, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router';
import LeadRenderer from '../hits/view/LeadRenderer';
import RecordQuery from '../hits/search/RecordQuery';
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

const SAMPLE_LEAD: Lead = {
  icon: 'material-symbols:find-in-page',
  format: 'markdown',
  label: { en: 'Investigation guide', fr: "Guide d'investigation" },
  content: 'Review the matching hit and confirm its investigation context.'
};

const SAMPLE_PIVOT: Pivot = {
  icon: 'material-symbols:link',
  format: 'link',
  label: { en: 'Open investigation tool', fr: "Ouvrir l'outil d'investigation" },
  value: 'https://investigate.example/?host={{hostname}}',
  mappings: [{ key: 'hostname', field: 'host.name' }]
};

const SAMPLE_DOSSIER: Dossier = {
  dossier_id: 'documentation-example',
  title: 'VPN Monitor',
  owner: 'analyst',
  type: 'global',
  query: 'howler.analytic:"VPN Monitor" AND howler.status:open',
  leads: [SAMPLE_LEAD],
  pivots: [SAMPLE_PIVOT]
};

const DossierDeliveryPreview: FC = () => {
  const { i18n, t } = useTranslation();
  const [tab, setTab] = useState('details');

  return (
    <Stack spacing={1}>
      <Tabs value={tab} onChange={(_, nextTab: string) => setTab(nextTab)}>
        <Tab label={t('hit.viewer.details')} value="details" />
        <Tab
          label={
            <Stack direction="row" spacing={0.5}>
              <Icon icon={SAMPLE_LEAD.icon!} />
              <span>{i18n.language === 'en' ? SAMPLE_LEAD.label?.en : SAMPLE_LEAD.label?.fr}</span>
            </Stack>
          }
          value="lead"
        />
      </Tabs>
      {tab === 'lead' && <LeadRenderer lead={SAMPLE_LEAD} />}
    </Stack>
  );
};

const DossierScopePreview: FC = () => {
  const { t } = useTranslation();
  const [scope, setScope] = useState<'global' | 'personal'>('global');

  return (
    <ToggleButtonGroup
      exclusive
      size="small"
      value={scope}
      onChange={(_, nextScope: 'global' | 'personal' | null) => nextScope && setScope(nextScope)}
    >
      <Tooltip title={t('route.dossiers.manager.global')}>
        <ToggleButton value="global">
          <Language fontSize="small" />
        </ToggleButton>
      </Tooltip>
      <Tooltip title={t('route.dossiers.manager.personal')}>
        <ToggleButton value="personal">
          <Person fontSize="small" />
        </ToggleButton>
      </Tooltip>
    </ToggleButtonGroup>
  );
};

const DossierDocumentation: FC = () => {
  const { i18n, t } = useTranslation();
  const theme = useTheme();
  const useHorizontal = useMediaQuery(theme.breakpoints.down(1700));
  useScrollRestoration();

  const sections = ['overview', 'query', 'leads', 'pivots', 'usage'] as const;
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = sections.find(section => section === searchParams.get('tab')) ?? 'overview';

  const onChange = useCallback(
    (nextTab: (typeof sections)[number]) => {
      const nextParams = new URLSearchParams(searchParams);
      nextParams.set('tab', nextTab);
      setSearchParams(nextParams);
    },
    [searchParams, setSearchParams]
  );

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
    dossier_delivery: <DossierDeliveryPreview />,
    dossier_scope: <DossierScopePreview />,
    dossier_query: <RecordQuery disabled triggerSearch={() => {}} />,
    dossier_lead: <LeadRenderer lead={SAMPLE_LEAD} />,
    dossier_pivot: <PivotLink pivot={SAMPLE_PIVOT} dossier={SAMPLE_DOSSIER} />
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
