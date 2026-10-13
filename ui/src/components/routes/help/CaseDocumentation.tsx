import { Box, Stack, Tab, Typography, useMediaQuery, useTheme } from '@mui/material';
import { PageCenter } from '@tui/core';
import Markdown from 'components/elements/display/Markdown';
import { useScrollRestoration } from 'components/hooks/useScrollRestoration';
import type { FC } from 'react';
import { useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router';
import {
  AddRecordsPreview,
  CaseControlsPreview,
  CaseDashboardPreview,
  CaseDetailsPreview,
  CaseFolderTreePreview,
  CaseInvestigationViewsPreview,
  CaseItemTypesPreview,
  CaseNavigationPreview,
  CaseTasksPreview,
  CorrelationRulePreview
} from './components/CaseDocumentationPreviews';
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

  const sections = ['overview', 'sidebar', 'summary', 'folders', 'records', 'items', 'investigation', 'rules'] as const;
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
  const documentationComponents = {
    case_navigation: <CaseNavigationPreview />,
    case_controls: <CaseControlsPreview />,
    case_details: <CaseDetailsPreview />,
    case_dashboard: <CaseDashboardPreview />,
    folder_tree: <CaseFolderTreePreview />,
    add_records: <AddRecordsPreview />,
    case_tasks: <CaseTasksPreview />,
    investigation_views: <CaseInvestigationViewsPreview />,
    correlation_rule: <CorrelationRulePreview />,
    case_item_types: <CaseItemTypesPreview />
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
