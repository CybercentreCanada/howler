import {
  Box,
  CardContent,
  IconButton,
  LinearProgress,
  Paper,
  Skeleton,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography
} from '@mui/material';
import api from 'api';
import PageCenter from 'commons/components/pages/PageCenter';
import TemplateEditor from 'components/routes/templates/TemplateEditor';
import { useCallback, useEffect, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';

import { ChevronLeft, ChevronRight, Language, Person } from '@mui/icons-material';
import HitSearchProvider, { HitSearchContext } from 'components/app/providers/HitSearchProvider';
import ParameterProvider, { ParameterContext } from 'components/app/providers/ParameterProvider';
import HowlerCard from 'components/elements/display/HowlerCard';
import QueryResultText from 'components/elements/display/QueryResultText';
import HitBanner from 'components/elements/hit/HitBanner';
import { HitLayout } from 'components/elements/hit/HitLayout';
import SaveButton from 'components/elements/SaveButton';
import useMyApi from 'components/hooks/useMyApi';
import { isEqual, isNil } from 'lodash-es';
import type { Template } from 'models/entities/generated/Template';
import { useParams } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import { setter } from 'utils/react';
import { sanitizeLuceneQuery } from 'utils/stringUtils';
import HitQuery from '../hits/search/HitQuery';

const _TemplateViewer = () => {
  const { t } = useTranslation();
  const params = useParams();
  const { dispatchApi } = useMyApi();

  const query = useContextSelector(ParameterContext, ctx => ctx.query);
  const setQuery = useContextSelector(ParameterContext, ctx => ctx.setQuery);

  const search = useContextSelector(HitSearchContext, ctx => ctx.search);
  const searching = useContextSelector(HitSearchContext, ctx => ctx.searching);
  const response = useContextSelector(HitSearchContext, ctx => ctx.response);

  const [loading, setLoading] = useState(false);
  const [searchDirty, setSearchDirty] = useState<boolean>(false);
  const [error, setError] = useState<string>(null);
  const [hitIndex, setHitIndex] = useState(0);

  const [originalTemplate, setOriginalTemplate] = useState<Template>(null);
  const [template, setTemplate] = useState<Template>(null);

  const onSave = useCallback(async () => {
    setLoading(true);
    try {
      setTemplate(await dispatchApi(params.id ? api.template.put(params.id, template) : api.template.post(template)));
    } finally {
      setLoading(false);
    }
  }, [dispatchApi, params.id, template]);

  const onSearchChange = useCallback((_query, _dirty) => {
    setTemplate(setter('query', _query));
    setSearchDirty(_dirty);
  }, []);

  useEffect(() => {
    if (response?.items.length < hitIndex) {
      setHitIndex(0);
    }
  }, [hitIndex, response?.items.length]);

  useEffect(() => {
    if (template?.analytic) {
      let _query = `howler.analytic:"${sanitizeLuceneQuery(template.analytic)}"`;

      if (template.detection) {
        _query += ` AND howler.detection:"${sanitizeLuceneQuery(template.detection)}"`;
      }

      setQuery(_query);
      setTemplate({
        ...template,
        analytic: null,
        detection: null,
        query: _query,
        name: template.name || `${template.analytic} - ${template.detection ?? t('all')}`
      });
    } else if (template?.query) {
      setQuery(template?.query);
    }

    // We use this as a check for if the template is old
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [template?.analytic]);

  useEffect(() => {
    setLoading(true);
    dispatchApi(api.search.template.post({ query: `template_id:${params.id}`, rows: 1 }))
      .then(result => {
        setTemplate(result.items[0]);
        setOriginalTemplate(result.items[0]);
      })
      .catch(err => setError(err.toString()))
      .finally(() => setLoading(false));
  }, [dispatchApi, params.id]);

  const selectedHit = response?.items?.[hitIndex];

  return (
    <PageCenter maxWidth="1000px" width="100%" textAlign="left" height="97%">
      <Box position="relative">
        <SaveButton
          save={onSave}
          disabled={loading || isEqual(originalTemplate, template) || searchDirty}
          error={error}
        />
        <Stack direction="column" spacing={1} height="100%">
          <Paper sx={{ p: 1 }}>
            <Stack direction="row" spacing={1} alignItems="stretch">
              {isNil(template?.name) ? (
                <Skeleton variant="rounded" height={40} width="100%" />
              ) : (
                <TextField
                  label={t('route.templates.name')}
                  size="small"
                  value={template?.name}
                  onChange={e => setTemplate(setter('name', e.target.value))}
                  fullWidth
                />
              )}
              <ToggleButtonGroup
                disabled={loading}
                exclusive
                value={template?.type ?? 'personal'}
                onChange={(__, type) => {
                  if (type) {
                    setTemplate(setter('type', type));
                  }
                }}
              >
                <Tooltip title={t('route.dossiers.manager.global')}>
                  <ToggleButton value="global" size="small">
                    <Language fontSize="small" />
                  </ToggleButton>
                </Tooltip>
                <Tooltip title={t('route.dossiers.manager.personal')}>
                  <ToggleButton value="personal" size="small">
                    <Person fontSize="small" />
                  </ToggleButton>
                </Tooltip>
              </ToggleButtonGroup>
            </Stack>

            <Typography
              sx={theme => ({
                color: theme.palette.text.secondary,
                fontSize: '0.9em',
                fontStyle: 'italic',
                mb: 0.5
              })}
              variant="body2"
            >
              {t('hit.search.prompt')}
            </Typography>

            {!template?.query ? (
              <Skeleton variant="rounded" height={56} />
            ) : (
              <HitQuery searching={searching} triggerSearch={_query => search(_query)} onChange={onSearchChange} />
            )}
            {response?.total >= 0 && <QueryResultText count={response?.total} query={query} />}
          </Paper>

          <LinearProgress sx={{ opacity: +searching }} />

          <Box sx={{ position: 'relative' }}>
            <IconButton
              sx={theme => ({ position: 'absolute', top: 0, right: `calc(100% + ${theme.spacing(1)})` })}
              onClick={() => setHitIndex(_index => _index - 1)}
              disabled={hitIndex < 1}
            >
              <ChevronLeft />
            </IconButton>
            <HowlerCard>
              <CardContent>
                {selectedHit ? (
                  <HitBanner hit={selectedHit} layout={HitLayout.NORMAL} />
                ) : (
                  <Stack>
                    <Skeleton variant="text" height={28} />
                    <Skeleton variant="text" width="80%" sx={{ alignSelf: 'center' }} />
                    <Skeleton variant="text" width="80%" sx={{ alignSelf: 'center' }} />
                  </Stack>
                )}
              </CardContent>
            </HowlerCard>
            <IconButton
              sx={theme => ({ position: 'absolute', top: 0, left: `calc(100% + ${theme.spacing(1)})` })}
              onClick={() => setHitIndex(_index => _index + 1)}
              disabled={hitIndex >= response?.items.length - 1}
            >
              <ChevronRight />
            </IconButton>
          </Box>
          <TemplateEditor
            hit={selectedHit}
            fields={template?.keys ?? []}
            setFields={fields => setTemplate(setter('keys', fields))}
          />
        </Stack>
      </Box>
    </PageCenter>
  );
};

const TemplateViewer: FC = () => {
  return (
    <ParameterProvider>
      <HitSearchProvider>
        <_TemplateViewer />
      </HitSearchProvider>
    </ParameterProvider>
  );
};

export default TemplateViewer;
