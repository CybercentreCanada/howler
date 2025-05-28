import {
  Autocomplete,
  Box,
  Button,
  CircularProgress,
  Divider,
  FormControl,
  LinearProgress,
  Stack,
  TextField,
  Tooltip,
  useTheme
} from '@mui/material';
import api from 'api';
import PageCenter from 'commons/components/pages/PageCenter';
import { useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Check, Delete, SsidChart } from '@mui/icons-material';
import hitsData from 'api/hit/:id/data/index.json';
import AppInfoPanel from 'commons/components/display/AppInfoPanel';
import { AnalyticContext } from 'components/app/providers/AnalyticProvider';
import { OverviewContext } from 'components/app/providers/OverviewProvider';
import HitOverview from 'components/elements/hit/HitOverview';
import useMyApi from 'components/hooks/useMyApi';
import type { Analytic } from 'models/entities/generated/Analytic';
import type { Hit } from 'models/entities/generated/Hit';
import type { Overview } from 'models/entities/generated/Overview';
import { useSearchParams } from 'react-router-dom';
import { sanitizeLuceneQuery } from 'utils/stringUtils';
import OverviewEditor from './OverviewEditor';
import { STARTING_TEMPLATE } from './startingTemplate';

const OverviewViewer = () => {
  const theme = useTheme();
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const { getOverviews } = useContext(OverviewContext);
  const { dispatchApi } = useMyApi();

  const [overviewList, setOverviewList] = useState<Overview[]>([]);
  const [selectedOverview, setSelectedOverview] = useState<Overview>(null);
  const [content, setContent] = useState<string>('');

  const [analytics, setAnalytics] = useState<Analytic[]>([]);
  const [detections, setDetections] = useState<string[]>([]);

  const [analytic, setAnalytic] = useState<string>(params.get('analytic') ?? '');
  const [detection, setDetection] = useState<string>(params.get('detection') ?? 'ANY');
  const [loading, setLoading] = useState(false);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [exampleHit, setExampleHit] = useState<Hit>(null);
  const [x, setX] = useState(0);

  const analyticContext = useContext(AnalyticContext);

  const wrapper = useRef<HTMLDivElement>();

  useEffect(() => {
    (async () => {
      setLoading(true);

      try {
        setOverviewList(await getOverviews(true));

        const analyticsResult = await dispatchApi(api.search.analytic.post({ query: 'analytic_id:*', rows: 1000 }), {
          logError: false,
          showError: true,
          throwError: true
        });

        const _analytics = analyticsResult.items;

        if (!_analytics.some(_analytic => _analytic.name.toLowerCase() === analytic.toLowerCase())) {
          setAnalytic('');
        }

        setAnalytics(_analytics);
      } finally {
        setLoading(false);
      }
    })();

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analytic, dispatchApi]);

  useEffect(() => {
    if (analytic) {
      setLoading(true);

      analyticContext
        .getAnalyticFromName(analytic)
        .then(foundAnalytic => {
          setDetections(foundAnalytic.detections);
        })
        .catch(() => {
          setDetection('ANY');
        })
        .finally(() => setLoading(false));
    }
  }, [analytic, analyticContext, detection, dispatchApi, params, setParams]);

  useEffect(() => {
    (async () => {
      const result = await dispatchApi(
        api.search.hit.post({
          query:
            `howler.analytic:"${sanitizeLuceneQuery(analytic)}"` +
            (!!detection && detection !== 'ANY' ? ` AND howler.detection:"${sanitizeLuceneQuery(detection)}"` : ''),
          rows: 1,
          fl: '*'
        }),
        { throwError: false, showError: false, logError: false }
      );

      if (result?.items[0]) {
        setExampleHit(result.items[0]);
        return;
      }

      const _hit = hitsData.GET[Object.keys(hitsData.GET)[0]];

      if (analytic) {
        _hit.howler.analytic = analytic;
      }

      if (detection) {
        _hit.howler.detection = detection;
      }

      setExampleHit(_hit);
    })();
  }, [analytic, detection, dispatchApi]);

  useEffect(() => {
    if (analytic && detection) {
      const overview = overviewList.find(
        _overview =>
          _overview.analytic === analytic &&
          ((detection === 'ANY' && !_overview.detection) || _overview.detection === detection)
      );

      if (overview) {
        setSelectedOverview(overview);
        setContent(overview.content);
      } else {
        setSelectedOverview(null);
        setContent('');
      }
    }
  }, [analytic, detection, overviewList]);

  useEffect(() => {
    if (analytic) {
      params.set('analytic', analytic);
    } else {
      params.delete('analytic');
    }

    if (detection && detection !== 'ANY') {
      params.set('detection', detection);
    } else {
      params.delete('detection');
    }

    params.sort();

    setParams(params, {
      replace: true
    });
  }, [analytic, detection, params, setParams]);

  const onDelete = useCallback(async () => {
    await dispatchApi(api.overview.del(selectedOverview.overview_id), {
      logError: false,
      showError: true,
      throwError: false
    });
    setSelectedOverview(null);
    setContent('');
  }, [dispatchApi, selectedOverview?.overview_id]);

  const onSave = useCallback(async () => {
    if (analytic && detection) {
      try {
        setOverviewLoading(true);
        const result = await dispatchApi(
          selectedOverview
            ? api.overview.put(selectedOverview.overview_id, content)
            : api.overview.post({
                analytic,
                detection: detection !== 'ANY' ? detection : null,
                content
              } as any),
          {
            logError: false,
            showError: true,
            throwError: true
          }
        );

        setSelectedOverview(result);
        const newList = [result, ...overviewList];
        setOverviewList(newList.filter((v1, i) => newList.findIndex(v2 => v1.overview_id === v2.overview_id) === i));
      } finally {
        setOverviewLoading(false);
      }
    }
  }, [analytic, detection, dispatchApi, selectedOverview, content, overviewList]);

  const onMouseMove = useCallback((event: MouseEvent) => {
    const wrapperRect = wrapper.current?.getBoundingClientRect();

    const offset = event.clientX - (wrapperRect.left + wrapperRect.width / 2);

    setX(offset);
  }, []);

  const onMouseUp = useCallback(() => {
    window.removeEventListener('mousemove', onMouseMove);
    window.removeEventListener('mouseup', onMouseUp);
  }, [onMouseMove]);

  const onMouseDown = useCallback(() => {
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
  }, [onMouseMove, onMouseUp]);

  const analyticOrDetectionMissing = useMemo(() => !analytic || !detection, [analytic, detection]);
  const noChange = useMemo(() => selectedOverview?.content === content, [content, selectedOverview?.content]);

  return (
    <PageCenter maxWidth="100%" width="100%" textAlign="left" height="100%">
      <LinearProgress sx={{ mb: 1, opacity: +loading }} />
      <Stack direction="column" spacing={2} divider={<Divider orientation="horizontal" flexItem />} height="100%">
        <Stack direction="row" spacing={2} mb={2} alignItems="stretch">
          <FormControl sx={{ maxWidth: { sm: '300px', lg: '450px' }, width: '100%' }}>
            <Autocomplete
              id="analytic"
              options={analytics.sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()))}
              getOptionLabel={option => option.name}
              value={analytics.find(a => a.name === analytic) || null}
              onChange={(_event, newValue) => setAnalytic(newValue ? newValue.name : '')}
              renderInput={autocompleteAnalyticParams => (
                <TextField {...autocompleteAnalyticParams} label={t('route.overviews.analytic')} size="small" />
              )}
            />
          </FormControl>
          {!analytics.find(_analytic => _analytic.name === analytic)?.rule ? (
            <FormControl sx={{ minWidth: { sm: '200px' } }} disabled={!analytic}>
              <Autocomplete
                id="detection"
                options={['ANY', ...detections.sort()]}
                getOptionLabel={option => option}
                value={detection ?? ''}
                onChange={(_event, newValue) => setDetection(newValue)}
                renderInput={autocompleteDetectionParams => (
                  <TextField {...autocompleteDetectionParams} label={t('route.overviews.detection')} size="small" />
                )}
              />
            </FormControl>
          ) : (
            <Tooltip title={t('route.overviews.rule.explanation')}>
              <SsidChart color="info" sx={{ alignSelf: 'center' }} />
            </Tooltip>
          )}
          {selectedOverview && (
            <Button variant="outlined" startIcon={<Delete />} onClick={onDelete}>
              {t('button.delete')}
            </Button>
          )}
          <Button
            variant="outlined"
            disabled={analyticOrDetectionMissing || noChange}
            startIcon={overviewLoading ? <CircularProgress size={16} /> : <Check />}
            onClick={onSave}
          >
            {t(!analyticOrDetectionMissing && !noChange ? 'button.save' : 'button.saved')}
          </Button>
        </Stack>
        {analyticOrDetectionMissing ? (
          <AppInfoPanel i18nKey="route.overviews.select" sx={{ width: '100%', alignSelf: 'start' }} />
        ) : (
          <Stack
            ref={wrapper}
            direction="row"
            spacing={1}
            height="100%"
            onKeyDown={e => {
              if (e.ctrlKey && e.key === 's') {
                if (!noChange) {
                  onSave();
                }
                e.preventDefault();
              }
            }}
            sx={{ position: 'relative' }}
          >
            <Box flex={1} position="relative" height="100%">
              <Box
                flex={1}
                sx={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  bottom: 0,
                  right: `calc(50% + 7px - ${x}px)`,
                  mr: -2.4,
                  pr: 1.5
                }}
              >
                <OverviewEditor height="100%" content={content} setContent={setContent} />
              </Box>
            </Box>
            <Box
              sx={{
                position: 'absolute',
                top: 0,
                bottom: 0,
                left: 'calc(50% - 5px)',
                width: '10px',
                backgroundColor: theme.palette.divider,
                cursor: 'col-resize',
                transform: `translateX(${x}px)`,
                zIndex: 1000,
                borderRadius: theme.shape.borderRadius
              }}
              onMouseDown={onMouseDown}
            />
            <Box
              flex={1}
              px={2}
              sx={{
                position: 'absolute',
                top: 0,
                left: `calc(50% + 7px + ${x}px)`,
                bottom: 0,
                right: 0,
                display: 'flex',
                alignItems: 'stretch',
                justifyContent: 'stretch',
                px: 1,
                pt: 1,
                mt: -1,
                '& > *': { width: '100%' },
                '& > div > :first-child': { mt: 0 }
              }}
            >
              <HitOverview content={content || STARTING_TEMPLATE} hit={exampleHit} />
            </Box>
          </Stack>
        )}
      </Stack>
    </PageCenter>
  );
};

export default OverviewViewer;
