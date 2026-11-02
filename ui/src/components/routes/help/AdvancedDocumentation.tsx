import { Box, Stack, Tab, Typography, useMediaQuery, useTheme } from '@mui/material';
import { PageCenter } from '@tui/core';
import Markdown from 'components/elements/display/Markdown';
import { useScrollRestoration } from 'components/hooks/useScrollRestoration';
import type { FC } from 'react';
import { useCallback, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router';
import {
  ExecuteQueryButton,
  FieldsControl,
  GroupByFieldSelect,
  type LuceneQueryType,
  LuceneQueryTypeSelect,
  OpenInSearchButton,
  QueryLanguageSelect,
  type QueryLanguage,
  RowsControl
} from '../advanced/QueryBuilderControls';
import HelpTabs from './components/HelpTabs';
import LANGUAGES_EN from './markdown/en/advancedLanguages.md';
import LUCENE_EN from './markdown/en/advancedLucene.md';
import OVERVIEW_EN from './markdown/en/advancedOverview.md';
import RESULTS_EN from './markdown/en/advancedResults.md';
import LANGUAGES_FR from './markdown/fr/advancedLanguages.md';
import LUCENE_FR from './markdown/fr/advancedLucene.md';
import OVERVIEW_FR from './markdown/fr/advancedOverview.md';
import RESULTS_FR from './markdown/fr/advancedResults.md';

const AdvancedDocumentation: FC = () => {
  const { i18n, t } = useTranslation();
  const theme = useTheme();
  const useHorizontal = useMediaQuery(theme.breakpoints.down(1700));
  const compactLayout = useMediaQuery('(max-width:870px)');
  useScrollRestoration();

  const [queryLanguage, setQueryLanguage] = useState<QueryLanguage>('lucene');
  const [queryType, setQueryType] = useState<LuceneQueryType>('default');
  const [groupByField, setGroupByField] = useState('howler.id');
  const [rows, setRows] = useState(1);
  const [allFields, setAllFields] = useState(true);
  const [fields, setFields] = useState<string[]>(['howler.id']);

  const onQueryLanguageChange = useCallback((language: QueryLanguage) => {
    setQueryLanguage(language);
    if (language !== 'lucene') {
      setQueryType('default');
    }
  }, []);

  const sections = ['overview', 'languages', 'lucene', 'results'] as const;
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
            languages: LANGUAGES_EN,
            lucene: LUCENE_EN,
            results: RESULTS_EN
          }
        : {
            overview: OVERVIEW_FR,
            languages: LANGUAGES_FR,
            lucene: LUCENE_FR,
            results: RESULTS_FR
          },
    [i18n.language]
  );

  const documentationComponents = {
    advanced_languages: (
      <QueryLanguageSelect value={queryLanguage} onChange={onQueryLanguageChange} compactLayout={compactLayout} />
    ),
    advanced_execute: (
      <Stack direction="row" spacing={1} alignItems="center">
        <ExecuteQueryButton
          loading={false}
          searchDisabled={queryType === 'groupby' && !groupByField}
          onExecute={() => {}}
        />
        <Typography variant="caption" color="text.secondary">
          {t('help.advanced.shortcut')}
        </Typography>
      </Stack>
    ),
    advanced_modes: (
      <Stack direction={compactLayout ? 'column' : 'row'} spacing={1} flexWrap="wrap">
        <LuceneQueryTypeSelect value={queryType} onChange={setQueryType} />
        {queryType === 'groupby' && (
          <GroupByFieldSelect
            options={['howler.id', 'howler.status', 'howler.analytic']}
            value={groupByField}
            onChange={setGroupByField}
          />
        )}
      </Stack>
    ),
    advanced_results: (
      <Stack direction={compactLayout ? 'column' : 'row'} spacing={1} alignItems="center" flexWrap="wrap">
        <RowsControl value={rows} onChange={setRows} />
        <FieldsControl
          allFields={allFields}
          onAllFieldsChange={setAllFields}
          queryType={queryType}
          fieldOptions={['howler.id', 'howler.status', 'howler.analytic']}
          fields={fields}
          onFieldsChange={setFields}
        />
        <OpenInSearchButton query="howler.status:open" hasResponse />
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
              label={<Typography variant="caption">{t(`help.advanced.${section}.title`)}</Typography>}
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

export default AdvancedDocumentation;
