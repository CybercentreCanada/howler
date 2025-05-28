import { iconExists } from '@iconify/react/dist/iconify.js';
import { Language, Person, Save } from '@mui/icons-material';
import {
  Box,
  CircularProgress,
  Fab,
  Paper,
  Stack,
  Tab,
  Tabs,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
  useMediaQuery
} from '@mui/material';
import api from 'api';
import PageCenter from 'commons/components/pages/PageCenter';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import useMyApi from 'components/hooks/useMyApi';
import { isEqual, omit, uniqBy } from 'lodash-es';
import type { Dossier } from 'models/entities/generated/Dossier';
import { memo, useCallback, useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import QueryResultText from '../../elements/display/QueryResultText';
import HitQuery from '../hits/search/HitQuery';
import LeadForm from './LeadForm';
import PivotForm from './PivotForm';

const DossierEditor: FC = () => {
  const { t, i18n } = useTranslation();
  const params = useParams();
  const { dispatchApi } = useMyApi();
  const navigate = useNavigate();

  const setQuery = useContextSelector(ParameterContext, ctx => ctx.setQuery);

  const isNarrow = useMediaQuery(`(max-width: ${i18n.language === 'en' ? 1275 : 1375}px)`);

  const [originalDossier, setOriginalDossier] = useState<Dossier>();
  const [dossier, setDossier] = useState<Partial<Dossier>>({
    type: 'global'
  });
  const [tab, setTab] = useState<'leads' | 'pivots'>('leads');
  const [searchTotal, setSearchTotal] = useState(-1);
  const [searchDirty, setSearchDirty] = useState(false);
  const [loading, setLoading] = useState(false);

  const dirty = useMemo(() => !isEqual(originalDossier, dossier), [dossier, originalDossier]);
  const validationError = useMemo(() => {
    if (!dossier || !dossier.query || !dossier.type || !dossier.title) {
      return t('route.dossiers.manager.validation.error');
    }

    if (!dossier.query) {
      return t('route.dossiers.manager.validation.error.missing', { field: 'query' });
    }

    if (!dossier.type) {
      return t('route.dossiers.manager.validation.error.missing', { field: 'type' });
    }

    if (!dossier.title) {
      return t('route.dossiers.manager.validation.error.missing', { field: 'title' });
    }

    if ((dossier.leads ?? []).length < 1 && (dossier.pivots ?? []).length < 1) {
      return t('route.dossiers.manager.validation.error.items');
    }

    if (
      !(dossier.leads ?? [])?.every(
        lead =>
          lead.icon &&
          iconExists(lead.icon) &&
          lead.label?.en &&
          lead.label?.fr &&
          lead.label &&
          lead.format &&
          lead.content
      )
    ) {
      return t('route.dossiers.manager.validation.error.leads');
    }

    if (
      !dossier.pivots?.every(
        pivot => pivot.icon && iconExists(pivot.icon) && pivot.label && pivot.label.en && pivot.label.fr && pivot.format
      )
    ) {
      return t('route.dossiers.manager.validation.error.pivots');
    }

    if (!dossier.pivots?.every(pivot => (pivot.mappings ?? []).length === uniqBy(pivot.mappings ?? [], 'key').length)) {
      return t('route.dossiers.manager.validation.error.pivots.duplicate');
    }

    return null;
  }, [dossier, t]);

  const save = useCallback(async () => {
    setLoading(true);

    try {
      if (!params.id) {
        const result = await dispatchApi(api.dossier.post(dossier));

        navigate(`/dossiers/${result.dossier_id}/edit`);
      } else {
        setDossier(await dispatchApi(api.dossier.put(dossier.dossier_id, omit(dossier, ['dossier_id', 'id']))));
      }
    } finally {
      setLoading(false);
    }
  }, [dispatchApi, dossier, navigate, params.id]);

  useEffect(() => {
    if (!params.id) {
      return;
    }

    setLoading(true);

    dispatchApi(api.dossier.get(params.id) as Promise<Dossier>)
      .then(_dossier => {
        setOriginalDossier(_dossier);
        setDossier(_dossier);
      })
      .finally(() => setLoading(false));
  }, [dispatchApi, params.id]);

  useEffect(() => {
    if (!dossier.query) {
      return;
    }

    setQuery(dossier.query);

    (async () => {
      setLoading(true);

      try {
        const result = await dispatchApi(api.search.hit.post({ query: dossier.query, rows: 0 }));

        setSearchTotal(result.total);
      } finally {
        setLoading(false);
      }
    })();
  }, [dispatchApi, dossier.query, setQuery]);

  return (
    <PageCenter maxWidth="1000px" width="100%" textAlign="left" height="97%">
      <Box position="relative" height="100%">
        <Tooltip title={validationError}>
          <Fab
            variant="extended"
            size="large"
            color="primary"
            disabled={!dirty || searchDirty || !!validationError || loading}
            sx={theme => ({
              textTransform: 'none',
              position: 'absolute',
              right: isNarrow ? theme.spacing(2) : `calc(100% + ${theme.spacing(2)})`,
              whiteSpace: 'nowrap',
              pointerEvents: 'initial !important',
              ...(isNarrow ? { bottom: theme.spacing(1) } : { top: 0 })
            })}
            onClick={save}
          >
            {loading ? <CircularProgress size={24} sx={{ mr: 1 }} /> : <Save sx={{ mr: 1 }} />}
            <Typography>{t('save')}</Typography>
          </Fab>
        </Tooltip>
        <Stack spacing={1} height="100%">
          <Paper sx={{ p: 1 }}>
            <Stack spacing={1}>
              <Stack spacing={1} direction="row">
                <TextField
                  disabled={!dossier || loading}
                  label="Title"
                  size="small"
                  value={dossier.title ?? ''}
                  onChange={ev => setDossier(_dossier => ({ ..._dossier, title: ev.target.value }))}
                  fullWidth
                />
                <ToggleButtonGroup
                  disabled={!dossier || loading}
                  exclusive
                  value={dossier.type ?? 'global'}
                  onChange={(_ev, type) => setDossier(_dossier => ({ ..._dossier, type }))}
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
              <HitQuery
                disabled={!dossier || loading}
                onChange={(_val, isDirty) => setSearchDirty(isDirty)}
                triggerSearch={query => setDossier(_dossier => ({ ..._dossier, query }))}
              />
              {searchTotal >= 0 && <QueryResultText count={searchTotal} query={dossier.query} />}
            </Stack>
          </Paper>
          <Tabs value={tab} onChange={(_ev, value) => setTab(value)}>
            <Tab label={t('route.dossiers.manager.tabs.leads')} value="leads" />
            <Tab label={t('route.dossiers.manager.tabs.pivots')} value="pivots" />
          </Tabs>
          {tab === 'leads' && <LeadForm dossier={dossier} setDossier={setDossier} loading={loading} />}
          {tab === 'pivots' && <PivotForm dossier={dossier} setDossier={setDossier} loading={loading} />}
        </Stack>
      </Box>
    </PageCenter>
  );
};

export default memo(DossierEditor);
