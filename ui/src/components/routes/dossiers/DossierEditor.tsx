import { Language, Person } from '@mui/icons-material';
import {
  Box,
  Paper,
  Stack,
  Tab,
  Tabs,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography
} from '@mui/material';
import api from 'api';
import PageCenter from 'commons/components/pages/PageCenter';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import SaveButton from 'components/elements/SaveButton';
import useMyApi from 'components/hooks/useMyApi';
import { isEqual, omit } from 'lodash-es';
import type { Dossier } from 'models/entities/generated/Dossier';
import { memo, useCallback, useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import QueryResultText from '../../elements/display/QueryResultText';
import HitQuery from '../hits/search/HitQuery';
import LeadForm from './LeadForm';
import PivotForm from './PivotForm';
import { useValidator } from './validator';

const DossierEditor: FC = () => {
  const { t } = useTranslation();
  const params = useParams();
  const { dispatchApi } = useMyApi();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const validate = useValidator();

  const setQuery = useContextSelector(ParameterContext, ctx => ctx.setQuery);

  const [originalDossier, setOriginalDossier] = useState<Dossier>();
  const [dossier, setDossier] = useState<Partial<Dossier>>({
    type: 'global',
    leads: [],
    pivots: []
  });
  const [tab, setTab] = useState<'leads' | 'pivots'>((searchParams.get('tab') as 'leads' | 'pivots') ?? 'leads');
  const [searchTotal, setSearchTotal] = useState(-1);
  const [searchDirty, setSearchDirty] = useState(false);
  const [loading, setLoading] = useState(false);

  const dirty = useMemo(() => !isEqual(originalDossier, dossier), [dossier, originalDossier]);
  const validationError = useMemo(
    () => validate(dossier, searchTotal, searchDirty),
    [dossier, searchDirty, searchTotal, validate]
  );

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

  useEffect(() => {
    if (searchParams.get('tab') !== tab) {
      searchParams.set('tab', tab);
    }

    setSearchParams(searchParams, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [setSearchParams, tab]);

  return (
    <PageCenter maxWidth="1000px" width="100%" textAlign="left" height="97%">
      <Box position="relative" height="100%">
        <SaveButton
          save={save}
          disabled={!dirty || !!validationError || loading}
          loading={loading}
          error={validationError}
        />
        <Stack spacing={1} height="100%">
          <Paper sx={{ p: 1 }}>
            <Stack spacing={1}>
              <Stack spacing={1} direction="row">
                <TextField
                  id="dossier-title"
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
