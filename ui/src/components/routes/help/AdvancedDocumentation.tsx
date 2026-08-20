import { Code, DataObject, GroupWork, PlayArrowOutlined, Search } from '@mui/icons-material';
import { Box, Chip, Paper, Stack, Tab, Typography, useMediaQuery, useTheme } from '@mui/material';
import PageCenter from 'commons/components/pages/PageCenter';
import Markdown from 'components/elements/display/Markdown';
import { useScrollRestoration } from 'components/hooks/useScrollRestoration';
import type { FC } from 'react';
import { useCallback, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';
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

  const sections = ['overview', 'languages', 'lucene', 'results'] as const;
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
      <Stack direction="row" spacing={1} flexWrap="wrap">
        <Chip icon={<Code />} label={t('route.advanced.query.lucene')} />
        <Chip icon={<Code />} label={t('route.advanced.query.eql')} />
        <Chip icon={<Code />} label={t('route.advanced.query.yaml')} />
      </Stack>
    ),
    advanced_execute: (
      <Paper variant="outlined" sx={{ p: 1, maxWidth: 500 }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <PlayArrowOutlined color="success" />
          <Typography variant="body2">{t('route.actions.execute')}</Typography>
          <Typography variant="caption" color="text.secondary">
            {t('help.advanced.shortcut')}
          </Typography>
        </Stack>
      </Paper>
    ),
    advanced_modes: (
      <Stack direction="row" spacing={1} flexWrap="wrap">
        {['default', 'facet', 'groupby', 'explain'].map(mode => (
          <Chip
            key={mode}
            icon={mode === 'groupby' ? <GroupWork /> : <DataObject />}
            label={t(`route.advanced.query.type.${mode}`)}
          />
        ))}
      </Stack>
    ),
    advanced_results: (
      <Paper variant="outlined" sx={{ p: 1, maxWidth: 500 }}>
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
          <DataObject fontSize="small" />
          <Chip size="small" label={t('route.advanced.fields.all')} />
          <Chip size="small" label={t('route.advanced.rows')} />
          <Chip size="small" icon={<Search />} label={t('route.advanced.open')} />
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
