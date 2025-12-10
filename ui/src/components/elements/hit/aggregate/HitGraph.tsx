import { CenterFocusWeak, Refresh } from '@mui/icons-material';
import {
  Alert,
  AlertTitle,
  Autocomplete,
  Box,
  Button,
  CircularProgress,
  IconButton,
  Stack,
  TextField,
  Tooltip,
  alpha,
  useTheme
} from '@mui/material';
import api from 'api';
import type { Chart, ChartDataset, ChartOptions } from 'chart.js';
import 'chartjs-adapter-dayjs-4';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { HitContext } from 'components/app/providers/HitProvider';
import { HitSearchContext } from 'components/app/providers/HitSearchProvider';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import useMyApi from 'components/hooks/useMyApi';
import useMyChart from 'components/hooks/useMyChart';
import dayjs from 'dayjs';
import { capitalize } from 'lodash-es';
import type { FC } from 'react';
import { useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { Scatter } from 'react-chartjs-2';
import { useTranslation } from 'react-i18next';
import { useContextSelector } from 'use-context-selector';
import { DEFAULT_QUERY } from 'utils/constants';
import { convertCustomDateRangeToLucene, convertDateToLucene, stringToColor } from 'utils/utils';

const MAX_ROWS = 2500;
const OVERRIDE_ROWS = 10000;
const MAX_QUERY_SIZE = 50000;
const FILTER_FIELDS = [
  'howler.analytic',
  'howler.status',
  'howler.escalation',
  'howler.assessment',
  'howler.detection'
];

const HitGraph: FC<{ query: string }> = ({ query }) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const { dispatchApi } = useMyApi();
  const { scatter } = useMyChart();
  const { config } = useContext(ApiConfigContext);

  const setSelected = useContextSelector(ParameterContext, ctx => ctx.setSelected);
  const setQuery = useContextSelector(ParameterContext, ctx => ctx.setQuery);
  const span = useContextSelector(ParameterContext, ctx => ctx.span);
  const startDate = useContextSelector(ParameterContext, ctx => ctx.startDate);
  const endDate = useContextSelector(ParameterContext, ctx => ctx.endDate);

  const selectedHits = useContextSelector(HitContext, ctx => ctx.selectedHits);
  const addHitToSelection = useContextSelector(HitContext, ctx => ctx.addHitToSelection);
  const removeHitFromSelection = useContextSelector(HitContext, ctx => ctx.removeHitFromSelection);

  const viewId = useContextSelector(HitSearchContext, ctx => ctx.viewId);
  const error = useContextSelector(HitSearchContext, ctx => ctx.error);
  const response = useContextSelector(HitSearchContext, ctx => ctx.response);

  const chartRef = useRef<Chart<'scatter'>>();

  const [loading, setLoading] = useState(false);
  const [filterField, setFilterField] = useState<string>(FILTER_FIELDS[0]);
  const [data, setData] = useState<ChartDataset<'scatter'>[]>([]);
  const [showWarning, setShowWarning] = useState(false);
  const [override, setOverride] = useState(false);
  const [disabled, setDisabled] = useState(false);
  const [searchTotal, setSearchTotal] = useState(0);

  const [escalationFilter, setEscalationFilter] = useState<string>(null);

  const performQuery = useCallback(async () => {
    setLoading(true);
    setSearchTotal(0);

    try {
      const filters: string[] = [];
      if (span && !span.endsWith('custom')) {
        filters.push(`event.created:${convertDateToLucene(span)}`);
      } else if (startDate && endDate) {
        filters.push(`event.created:${convertCustomDateRangeToLucene(startDate, endDate)}`);
      }

      if (escalationFilter) {
        filters.push(`howler.escalation:${escalationFilter}`);
      }

      const total = (
        await dispatchApi(
          api.search.count.hit.post({
            query,
            filters
          })
        )
      ).count;

      if (total > MAX_QUERY_SIZE) {
        setDisabled(true);
        setSearchTotal(total);
        return;
      } else {
        setDisabled(false);
      }

      const _data = await dispatchApi(
        api.search.grouped.hit.post(filterField, {
          query: query || DEFAULT_QUERY,
          fl: 'event.created,howler.assessment,howler.analytic,howler.detection,howler.outline.threat,howler.outline.target,howler.outline.summary,howler.id',
          // We want a generally random sample across all date ranges, so we use hash.
          // If we used event.created instead, when 1 million hits/hour are created, you'd only see hits from this past minute
          sort: 'howler.hash desc',
          group_sort: 'howler.hash desc',
          limit: override ? OVERRIDE_ROWS : MAX_ROWS,
          rows: override ? OVERRIDE_ROWS : MAX_ROWS,
          filters
        })
      );

      if (_data.total > MAX_ROWS && !override) {
        setShowWarning(true);
      }

      const processed = _data.items.map(category => {
        const label = capitalize(category.value ?? 'None');

        return {
          label: `${label} (${category.total})`,
          data: category.items.map(hit => {
            const createdDate = dayjs(hit.event?.created ?? hit.timestamp);

            return {
              x: createdDate.clone().hour(0).minute(0).second(0).toISOString(),
              y: createdDate.hour() + createdDate.minute() / 60 + createdDate.second() / 3600,
              hit,
              label
            };
          }) as any[]
        };
      });

      setData(processed);
    } finally {
      setLoading(false);
    }
  }, [dispatchApi, endDate, escalationFilter, filterField, override, query, span, startDate]);

  useEffect(() => {
    if ((!query && !viewId) || error || !response) {
      return;
    }

    performQuery();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, viewId, error, span, response]);

  const options: ChartOptions<'scatter'> = useMemo(() => {
    const parentOptions = scatter('hit.summary.title', 'hit.summary.subtitle');

    return {
      ...parentOptions,
      animation: false,
      onClick: (event, elements) => {
        const ids = elements.map(({ element }) => (element as any).$context?.raw.hit?.howler.id).filter(id => !!id);
        if (ids.length < 1) {
          return;
        }

        if ((event.native as MouseEvent).ctrlKey || (event.native as MouseEvent).shiftKey) {
          ids.forEach(id => {
            if (selectedHits.some(hit => hit.howler.id === id)) {
              removeHitFromSelection(id);
            } else {
              addHitToSelection(id);
            }
          });
        } else {
          if (ids.length < 2) {
            setSelected(ids[0]);
          } else {
            setQuery(`howler.id:(${ids.join(' OR ')})`);
          }
        }
      },
      onHover: (event, chartElement) =>
        ((event.native.target as any).style.cursor = chartElement[0] ? 'pointer' : 'default'),
      interaction: {
        mode: 'nearest'
      },
      plugins: {
        ...parentOptions.plugins,
        tooltip: {
          callbacks: {
            title: entries => `${entries.length} ${t('hits')}`,
            label: entry =>
              `${(entry.raw as any).hit.howler.analytic}: ${(entry.raw as any).hit.howler.detection} (${dayjs(
                (entry.raw as any).hit.event.created
              ).format('MMM D HH:mm:ss')})`,
            afterLabel: entry =>
              `${(entry.raw as any).hit.howler.outline.threat} ${(entry.raw as any).hit.howler.outline.target}`
          }
        },
        zoom: {
          ...parentOptions.plugins.zoom,
          zoom: {
            ...parentOptions.plugins.zoom.zoom,
            mode: 'y'
          },
          limits: {
            y: { min: 0, max: 24 }
          }
        }
      },
      scales: {
        ...parentOptions.scales,
        y: {
          ...parentOptions.scales.y,
          grid: {
            display: true,
            color: theme.palette.divider
          },
          ticks: {
            callback: (value: number) => {
              const [hour, minute] = [Math.floor(value), Math.floor((value - Math.floor(value)) * 60)];

              return dayjs().hour(hour).minute(minute).format('HH:mm');
            }
          }
        }
      },
      elements: {
        point: {
          borderWidth: context => {
            return selectedHits.some(hit => hit.howler.id === (context.raw as any).hit?.howler.id) ? 2 : 0;
          },
          backgroundColor: context => {
            return alpha(stringToColor((context.raw as any).label), 0.6);
          },
          borderColor: theme.palette.success.light,
          pointRadius: 5
        }
      }
    };
  }, [
    addHitToSelection,
    removeHitFromSelection,
    scatter,
    selectedHits,
    setQuery,
    setSelected,
    t,
    theme.palette.divider,
    theme.palette.success.light
  ]);

  useEffect(() => {
    chartRef.current?.update();
  }, [selectedHits]);

  return (
    <Stack sx={{ position: 'relative' }} spacing={1}>
      <Scatter
        ref={chartRef}
        options={options}
        data={{
          datasets: data
        }}
      />
      <Stack direction="row" spacing={1} sx={{ pt: 2 }}>
        <Autocomplete
          sx={{ flex: 1 }}
          options={FILTER_FIELDS}
          renderInput={params => <TextField {...params} label={t('hit.summary.filter.field')} size="small" />}
          value={filterField}
          onChange={(__, option) => setFilterField(option)}
        />
        <Autocomplete
          sx={{ flex: 1 }}
          options={config.lookups['howler.escalation']}
          renderInput={params => <TextField {...params} label={t('hit.summary.filter.escalation')} size="small" />}
          value={escalationFilter}
          onChange={(__, option) => setEscalationFilter(option)}
        />
      </Stack>
      {showWarning && (
        <Alert
          severity="warning"
          variant="outlined"
          action={
            <Button
              variant="outlined"
              color="warning"
              onClick={() => {
                setOverride(true);
                setShowWarning(false);
              }}
            >
              {t('hit.summary.render.limit.override')}
            </Button>
          }
        >
          <AlertTitle>{t('hit.summary.render.limit', { number: MAX_ROWS })}</AlertTitle>
          {t(`hit.summary.render.limit.description`, { number: MAX_ROWS, max: OVERRIDE_ROWS })}
        </Alert>
      )}
      {disabled && (
        <Box
          sx={{
            position: 'absolute',
            top: theme.spacing(-1),
            bottom: 0,
            left: 0,
            right: 0,
            backgroundColor: alpha(theme.palette.background.paper, 0.75),
            zIndex: 11,
            display: 'flex',
            alignItems: 'start'
          }}
        >
          <Alert
            severity="warning"
            variant="outlined"
            sx={{ m: 3, mr: 7, backgroundColor: theme.palette.background.paper }}
          >
            <AlertTitle>{t('hit.summary.server.limit', { number: searchTotal })}</AlertTitle>
            {t(`hit.summary.server.limit.description`, { max: MAX_QUERY_SIZE })}
          </Alert>
        </Box>
      )}
      <Stack direction="row" sx={{ position: 'absolute', right: theme.spacing(1), top: 0, zIndex: 12 }} spacing={1}>
        <Tooltip title={t('hit.summary.zoom.reset')}>
          <IconButton disabled={loading} onClick={() => chartRef.current?.resetZoom()}>
            <CenterFocusWeak />
          </IconButton>
        </Tooltip>
        <Tooltip title={t('hit.summary.refresh')}>
          <IconButton disabled={loading} onClick={performQuery}>
            {loading ? <CircularProgress size={20} /> : <Refresh />}
          </IconButton>
        </Tooltip>
      </Stack>
    </Stack>
  );
};

export default HitGraph;
