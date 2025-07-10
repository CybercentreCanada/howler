import {
  Autocomplete,
  Button,
  CircularProgress,
  Divider,
  FormControl,
  LinearProgress,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip
} from '@mui/material';
import api from 'api';
import PageCenter from 'commons/components/pages/PageCenter';
import TemplateEditor from 'components/routes/templates/TemplateEditor';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Check, Delete, SsidChart } from '@mui/icons-material';
import AppInfoPanel from 'commons/components/display/AppInfoPanel';
import { DEFAULT_FIELDS } from 'components/elements/hit/HitOutline';
import useMyApi from 'components/hooks/useMyApi';
import isEqual from 'lodash-es/isEqual';
import type { Analytic } from 'models/entities/generated/Analytic';
import type { Hit } from 'models/entities/generated/Hit';
import type { Template } from 'models/entities/generated/Template';
import { useSearchParams } from 'react-router-dom';
import hitsData from 'utils/hit.json';
import { sanitizeLuceneQuery } from 'utils/stringUtils';

const TemplateViewer = () => {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const { dispatchApi } = useMyApi();

  const [templateList, setTemplateList] = useState<Template[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<Template>(null);
  const [displayFields, setDisplayFields] = useState<string[]>([]);

  const [analytics, setAnalytics] = useState<Analytic[]>([]);
  const [detections, setDetections] = useState<string[]>([]);

  const [analytic, setAnalytic] = useState<string>(params.get('analytic') ?? '');
  const [detection, setDetection] = useState<string>(params.get('detection') ?? 'ANY');
  const [type, setType] = useState<string>((params.get('type') ?? 'personal').replace('readonly', 'global'));
  const [loading, setLoading] = useState(false);
  const [templateLoading, setTemplateLoading] = useState(false);

  useEffect(() => {
    setLoading(true);

    dispatchApi(api.search.analytic.post({ query: 'analytic_id:*', rows: 1000 }), {
      logError: false,
      showError: true,
      throwError: true
    })
      .finally(() => setLoading(false))
      .then(result => result.items)
      .then(_analytics => {
        if (!_analytics.some(_analytic => _analytic.name.toLowerCase() === analytic.toLowerCase())) {
          setAnalytic('');
        }

        setAnalytics(_analytics);
      });

    dispatchApi(api.template.get()).then(setTemplateList);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analytic, dispatchApi]);

  useEffect(() => {
    if (analytic) {
      setLoading(true);

      dispatchApi(
        api.search.grouped.hit.post('howler.detection', {
          limit: 0,
          query: `howler.analytic:"${sanitizeLuceneQuery(analytic)}"`
        }),
        {
          logError: false,
          showError: true,
          throwError: true
        }
      )
        .finally(() => setLoading(false))
        .then(result => result.items.map(i => i.value))
        .then(_detections => {
          if (_detections.length < 1) {
            setDetection('ANY');
          }

          if (detection && !_detections.includes(detection)) {
            setDetection('ANY');
          }

          setDetections(_detections);
        });
    }
  }, [analytic, detection, dispatchApi, params, setParams, type]);

  useEffect(() => {
    if (analytic && detection) {
      const template = (templateList ?? []).find(
        _template =>
          _template.analytic === analytic &&
          ((detection === 'ANY' && !_template.detection) || _template.detection === detection) &&
          _template.type === type
      );

      if (template) {
        setSelectedTemplate(template);
        setDisplayFields(template.keys);
      } else {
        setSelectedTemplate(null);
        setDisplayFields(DEFAULT_FIELDS);
      }
    }
  }, [analytic, detection, templateList, type]);

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

    params.set('type', type);

    params.sort();

    setParams(params, {
      replace: true
    });
  }, [analytic, detection, params, setParams, type]);

  const exampleHit = useMemo<Hit>(() => {
    const _hit = hitsData.GET[Object.keys(hitsData.GET)[0]];

    if (analytic) {
      _hit.howler.analytic = analytic;
    }

    return { ..._hit };
  }, [analytic]);

  const onDelete = useCallback(async () => {
    await dispatchApi(api.template.del(selectedTemplate.template_id), {
      logError: false,
      showError: true,
      throwError: false
    });
    setSelectedTemplate(null);
    setDisplayFields(DEFAULT_FIELDS);
  }, [dispatchApi, selectedTemplate?.template_id]);

  const onSave = useCallback(async () => {
    if (analytic && detection) {
      try {
        setTemplateLoading(true);
        const result = await dispatchApi(
          selectedTemplate
            ? api.template.put(selectedTemplate.template_id, displayFields)
            : api.template.post({
                analytic,
                detection: detection !== 'ANY' ? detection : null,
                type,
                keys: displayFields
              }),
          {
            logError: false,
            showError: true,
            throwError: true
          }
        );

        setSelectedTemplate(result);
        const newList = [result, ...templateList];
        setTemplateList(newList.filter((v1, i) => newList.findIndex(v2 => v1.template_id === v2.template_id) === i));
      } finally {
        setTemplateLoading(false);
      }
    }
  }, [analytic, detection, dispatchApi, displayFields, selectedTemplate, templateList, type]);

  const analyticOrDetectionMissing = useMemo(() => !analytic || !detection, [analytic, detection]);
  const noFieldChange = useMemo(
    () => displayFields.length < 1 || isEqual(selectedTemplate?.keys ?? DEFAULT_FIELDS, displayFields),
    [displayFields, selectedTemplate?.keys]
  );

  return (
    <PageCenter maxWidth="1500px" textAlign="left" height="100%">
      <LinearProgress sx={{ mb: 1, opacity: +loading }} />
      <Stack direction="column" spacing={2} divider={<Divider orientation="horizontal" flexItem />} height="100%">
        <Stack direction="row" spacing={2} mb={2} alignItems="stretch">
          <FormControl sx={{ flex: 1, maxWidth: '450px' }}>
            <Autocomplete
              id="analytic"
              options={analytics.sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()))}
              getOptionLabel={option => option.name}
              value={analytics.find(a => a.name === analytic) || null}
              onChange={(__, newValue) => setAnalytic(newValue ? newValue.name : '')}
              renderInput={autocompleteAnalyticParams => (
                <TextField {...autocompleteAnalyticParams} label={t('route.templates.analytic')} size="small" />
              )}
            />
          </FormControl>
          {!(detections?.length < 2 && detections[0]?.toLowerCase() === 'rule') ? (
            <FormControl sx={{ flex: 1, maxWidth: '300px' }} disabled={!analytic}>
              <Autocomplete
                id="detection"
                options={['ANY', ...detections.sort()]}
                getOptionLabel={option => option}
                value={detection ?? ''}
                onChange={(__, newValue) => setDetection(newValue)}
                renderInput={autocompleteDetectionParams => (
                  <TextField {...autocompleteDetectionParams} label={t('route.templates.detection')} size="small" />
                )}
              />
            </FormControl>
          ) : (
            <Tooltip title={t('route.templates.rule.explanation')}>
              <SsidChart color="info" sx={{ alignSelf: 'center' }} />
            </Tooltip>
          )}
          <ToggleButtonGroup
            sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}
            size="small"
            exclusive
            value={type}
            disabled={analyticOrDetectionMissing}
            onChange={(__, _type) => {
              if (_type) {
                setType(_type);
              }
            }}
          >
            <ToggleButton sx={{ flex: 1 }} value="personal" aria-label="personal">
              {t('route.templates.personal')}
            </ToggleButton>
            <ToggleButton sx={{ flex: 1 }} value="global" aria-label="global">
              {t('route.templates.global')}
            </ToggleButton>
          </ToggleButtonGroup>
          {selectedTemplate && (
            <Button variant="outlined" startIcon={<Delete />} onClick={onDelete}>
              {t('button.delete')}
            </Button>
          )}
          <Button
            variant="outlined"
            disabled={analyticOrDetectionMissing || noFieldChange}
            startIcon={templateLoading ? <CircularProgress size={16} /> : <Check />}
            onClick={onSave}
          >
            {t(!analyticOrDetectionMissing && !noFieldChange ? 'button.save' : 'button.saved')}
          </Button>
        </Stack>
        {analyticOrDetectionMissing ? (
          <AppInfoPanel i18nKey="route.templates.select" sx={{ width: '100%', alignSelf: 'start' }} />
        ) : (
          <TemplateEditor
            hit={exampleHit}
            fields={displayFields}
            setFields={setDisplayFields}
            onAdd={field => setDisplayFields([...displayFields, field])}
            onRemove={field => setDisplayFields(displayFields.filter(f => f !== field))}
          />
        )}
      </Stack>
    </PageCenter>
  );
};

export default TemplateViewer;
