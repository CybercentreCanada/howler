import { Analytics, InfoOutlined } from '@mui/icons-material';
import {
  Alert,
  AlertTitle,
  Autocomplete,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  Fade,
  Grid,
  LinearProgress,
  Stack,
  TextField,
  Tooltip,
  Typography
} from '@mui/material';
import api from 'api';
import type { HowlerSearchResponse } from 'api/search';
import useMatchers from 'components/app/hooks/useMatchers';
import { FieldContext } from 'components/app/providers/FieldProvider';
import { HitSearchContext } from 'components/app/providers/HitSearchProvider';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import useMyApi from 'components/hooks/useMyApi';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import useMySnackbar from 'components/hooks/useMySnackbar';
import { isEmpty } from 'lodash-es';
import type { Hit } from 'models/entities/generated/Hit';
import type { WithMetadata } from 'models/WithMetadata';
import type { FC } from 'react';
import { memo, useCallback, useContext, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useContextSelector } from 'use-context-selector';
import { StorageKey } from 'utils/constants';
import { getTimeRange } from 'utils/utils';
import PluginChip from '../PluginChip';
import HitGraph from './aggregate/HitGraph';

const HitSummary: FC<{
  response?: HowlerSearchResponse<WithMetadata<Hit>>;
  execute?: boolean;
  onStart?: () => void;
  onComplete?: () => void;
}> = ({ response, onStart, onComplete }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const { hitFields } = useContext(FieldContext);
  const { showErrorMessage } = useMySnackbar();
  const pageCount = useMyLocalStorageItem(StorageKey.PAGE_COUNT, 25)[0];
  const { getMatchingTemplate } = useMatchers();

  const searching = useContextSelector(HitSearchContext, ctx => ctx.searching);
  const error = useContextSelector(HitSearchContext, ctx => ctx.error);
  const getFilters = useContextSelector(HitSearchContext, ctx => ctx.getFilters);

  const query = useContextSelector(ParameterContext, ctx => ctx.query);
  const setQuery = useContextSelector(ParameterContext, ctx => ctx.setQuery);
  const views = useContextSelector(ParameterContext, ctx => ctx.views);

  const [loading, setLoading] = useState(false);
  const [customKeys, setCustomKeys] = useState<string[]>([]);
  const [keyCounts, setKeyCounts] = useState<{ [key: string]: { count: number; sources: string[] } }>({});
  const [aggregateResults, setAggregateResults] = useState<{
    [key: string]: { [value: string]: number };
  }>({});

  const performAggregation = useCallback(async () => {
    if (onStart) {
      onStart();
    }

    try {
      // Get a list of every key in every template of the hits we're searching
      const rawCounts = await Promise.all(
        (response?.items ?? []).map(async h => {
          const matchingTemplate = await getMatchingTemplate(h);

          return (matchingTemplate?.keys ?? [])
            .filter(key => !['howler.id', 'howler.hash'].includes(key))
            .map(key => ({
              key,
              source: `${matchingTemplate.analytic}: ${matchingTemplate.detection ?? t('any')}`
            }));
        })
      );

      const _keyCounts = rawCounts
        .flat()
        .concat(customKeys.map(key => ({ key, source: 'custom' })))

        // Take that array and reduce it to unique keys and the number of times we see it,
        // as well as the templates we sourced this key from
        .reduce(
          (acc, val) => {
            if (acc[val.key] && val.source !== 'custom') {
              acc[val.key].count++;
            } else if (val.source === 'custom') {
              acc[val.key] = {
                count: -1,
                sources: [val.source]
              };
            } else {
              acc[val.key] = {
                count: 1,
                sources: [val.source]
              };
            }

            return acc;
          },
          {} as { [index: string]: { count: number; sources: string[] } }
        );

      // We'll save this for later
      setKeyCounts(_keyCounts);
      setAggregateResults({});

      // Sort the fields based on the number of occurrences
      const sortedKeys = Object.keys(_keyCounts).sort(
        (a, b) => (_keyCounts[b]?.count ?? 0) - (_keyCounts[a]?.count ?? 0)
      );

      if (sortedKeys.length > 0) {
        setLoading(true);
        const result = await dispatchApi(
          api.search.facet.hit.post({
            fields: sortedKeys,
            query,
            rows: pageCount,
            filters: await getFilters()
          }),
          {
            throwError: false,
            logError: true,
            showError: false
          }
        );

        if (result) {
          setAggregateResults(_results => ({
            ..._results,
            ...result
          }));
        }
      }
    } catch (e) {
      showErrorMessage(e);
      setAggregateResults({});
    } finally {
      setLoading(false);
      if (onComplete) {
        onComplete();
      }
    }
  }, [
    customKeys,
    dispatchApi,
    getFilters,
    getMatchingTemplate,
    onComplete,
    onStart,
    pageCount,
    query,
    response?.items,
    showErrorMessage,
    t
  ]);

  const setSearch = useCallback(
    (key, value) => {
      setQuery(`${key}:${value}`);
    },
    [setQuery]
  );

  useEffect(() => {
    if ((!query && views?.length < 1) || searching || error) {
      return;
    }

    performAggregation();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, views, searching, error]);

  return (
    <Stack sx={{ mx: 2, height: '100%' }} spacing={1}>
      <Typography variant="h6">{t('hit.summary.aggregate.title')}</Typography>
      <Divider flexItem />
      <HitGraph />
      <Divider flexItem />
      <Stack sx={{ overflow: 'auto', marginTop: '0 !important' }} pt={1} spacing={1}>
        <Stack direction="row" spacing={2} mb={2} alignItems="stretch">
          <Autocomplete
            fullWidth
            multiple
            sx={{ minWidth: '175px' }}
            size="small"
            value={customKeys}
            options={hitFields.map(_field => _field.key)}
            renderInput={_params => <TextField {..._params} label={t('hit.summary.adhoc')} />}
            onChange={(_, value) => setCustomKeys(value)}
          />
          <Button
            variant="outlined"
            startIcon={loading ? <CircularProgress size={20} sx={{ ml: 1 }} /> : <Analytics sx={{ ml: 1 }} />}
            disabled={loading}
            onClick={() => performAggregation()}
          >
            {t('button.aggregate')}
          </Button>
        </Stack>
        {isEmpty(aggregateResults) && (
          <Alert severity="info" variant="outlined">
            <AlertTitle>{t('hit.summary.aggregate.nokeys.title')}</AlertTitle>
            {t('hit.summary.aggregate.nokeys.description')}
          </Alert>
        )}
        {loading && <LinearProgress sx={{ minHeight: '4px' }} />}
        {Object.keys(aggregateResults)
          .filter(key => !isEmpty(aggregateResults[key]))
          .flatMap(key => [
            <Fade in key={key + '-refs'}>
              <Stack direction="row" alignItems="center" spacing={1}>
                <Typography key={key + '-title'} variant="body1">
                  {key}
                </Typography>
                {keyCounts[key]?.count < 0 ? (
                  <Typography variant="caption" color="text.secondary">
                    ({t('hit.summary.adhoc.custom')})
                  </Typography>
                ) : (
                  <Typography variant="caption" color="text.secondary">
                    ({keyCounts[key]?.count ?? '?'} {t('references')})
                  </Typography>
                )}

                <Tooltip
                  title={
                    <Stack>
                      <Typography variant="caption">{t('hit.summary.aggregate.sources')}</Typography>
                      {keyCounts[key]?.sources.map(source => (
                        <Typography key={source} variant="caption">
                          {source}
                        </Typography>
                      )) ?? '?'}
                    </Stack>
                  }
                >
                  <InfoOutlined fontSize="inherit" />
                </Tooltip>
              </Stack>
            </Fade>,
            <Fade in key={key + '-results'}>
              {hitFields.find(f => f.key === key)?.type !== 'date' ? (
                <Box sx={theme => ({ ml: `${theme.spacing(1)} !important`, alignSelf: 'start' })}>
                  <Grid container key={key + '-list'} sx={theme => ({ mr: 1, mt: theme.spacing(-1) })} spacing={1}>
                    {Object.keys(aggregateResults[key]).map(item => (
                      <Grid key={item} item xs="auto">
                        <PluginChip
                          context="summary"
                          size="small"
                          variant="filled"
                          value={item}
                          label={`${item} (${aggregateResults[key][item]})`}
                          onClick={() => setSearch(key, `"${item}"`)}
                          field={key}
                        />
                      </Grid>
                    ))}
                  </Grid>
                </Box>
              ) : (
                <Chip
                  size="small"
                  sx={theme => ({ ml: `${theme.spacing(1)} !important`, alignSelf: 'start' })}
                  label={getTimeRange(Object.keys(aggregateResults[key]))
                    .map(d => new Date(d).toLocaleString())
                    .join(' - ')}
                  onClick={() => setSearch(key, `[${getTimeRange(Object.keys(aggregateResults[key])).join(' TO ')}]`)}
                />
              )}
            </Fade>
          ])}
      </Stack>
    </Stack>
  );
};

export default memo(HitSummary);
