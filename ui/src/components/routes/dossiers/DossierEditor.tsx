import { iconExists } from '@iconify/react';
import { Language, Person, PersonAdd, Save } from '@mui/icons-material';
import {
  Box,
  CircularProgress,
  Fab,
  IconButton,
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
import { useAppUser } from 'commons/components/app/hooks';
import PageCenter from 'commons/components/pages/PageCenter';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import { MembershipManagement } from 'components/elements/membershipManagement';
import useMyApi from 'components/hooks/useMyApi';
import useMySnackbar from 'components/hooks/useMySnackbar';
import { isEqual, uniqBy } from 'lodash-es';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { HowlerUser } from 'models/entities/HowlerUser';
import { memo, useCallback, useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import QueryResultText from '../../elements/display/QueryResultText';
import HitQuery from '../hits/search/HitQuery';
import LeadForm from './LeadForm';
import PivotForm from './PivotForm';

const DossierEditor: FC = () => {
  const { t, i18n } = useTranslation();
  const params = useParams();
  const { dispatchApi } = useMyApi();
  const { showSuccessMessage } = useMySnackbar();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const appUser = useAppUser<HowlerUser>();
  const user = appUser?.user;
  const setQuery = useContextSelector(ParameterContext, ctx => ctx.setQuery);

  const isNarrow = useMediaQuery(`(max-width: ${i18n.language === 'en' ? 1275 : 1375}px)`);

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
  const [memberModalOpen, setMemberModalOpen] = useState(false);

  const dirty = useMemo(() => !isEqual(originalDossier, dossier), [dossier, originalDossier]);

  // Permission Check Logic
  const canManageMembership = useMemo(() => {
    if (!user || !dossier) return false;
    return dossier.owner === user.username || user.roles?.includes('admin');
  }, [user, dossier]);

  const validationError = useMemo(() => {
    if (!dossier) {
      return t('route.dossiers.manager.validation.error');
    }

    if (!dossier.title) {
      return t('route.dossiers.manager.validation.error.missing', { field: t('route.dossiers.manager.field.title') });
    }

    if (searchTotal < 0 || searchDirty) {
      return t('route.dossiers.manager.validation.search');
    }

    if (!dossier.query) {
      return t('route.dossiers.manager.validation.error.missing', { field: t('route.dossiers.manager.field.query') });
    }

    if (!dossier.type) {
      return t('route.dossiers.manager.validation.error.missing', { field: t('route.dossiers.manager.field.type') });
    }

    if ((dossier.leads ?? []).length < 1 && (dossier.pivots ?? []).length < 1) {
      return t('route.dossiers.manager.validation.error.items');
    }

    for (const lead of dossier.leads ?? []) {
      if (!lead.label) {
        return t('route.dossiers.manager.validation.error.leads.label');
      }

      if (!lead.label.en) {
        return t('route.dossiers.manager.validation.error.leads.label.en');
      }

      if (!lead.label.fr) {
        return t('route.dossiers.manager.validation.error.leads.label.fr');
      }

      if (!lead.format) {
        return t('route.dossiers.manager.validation.error.leads.format', { label: lead.label[i18n.language] });
      }

      if (!lead.content) {
        return t('route.dossiers.manager.validation.error.leads.content', { label: lead.label[i18n.language] });
      }

      if (!lead.icon || !iconExists(lead.icon)) {
        return t('route.dossiers.manager.validation.error.leads.icon', { label: lead.label[i18n.language] });
      }
    }

    for (const pivot of dossier.pivots ?? []) {
      if (!pivot.label) {
        return t('route.dossiers.manager.validation.error.pivots.label');
      }

      if (!pivot.label.en) {
        return t('route.dossiers.manager.validation.error.pivots.label.en');
      }

      if (!pivot.label.fr) {
        return t('route.dossiers.manager.validation.error.pivots.label.fr');
      }

      if (!pivot.format) {
        return t('route.dossiers.manager.validation.error.pivots.format', { label: pivot.label[i18n.language] });
      }

      if (!pivot.value) {
        return t('route.dossiers.manager.validation.error.pivots.value', { label: pivot.label[i18n.language] });
      }

      if (!pivot.icon || !iconExists(pivot.icon)) {
        return t('route.dossiers.manager.validation.error.pivots.icon', { label: pivot.label[i18n.language] });
      }

      if (!pivot.mappings || pivot.mappings.length < 1) {
        continue;
      }

      if ((pivot.mappings ?? []).length !== uniqBy(pivot.mappings ?? [], 'key').length) {
        return t('route.dossiers.manager.validation.error.pivots.duplicate', { label: pivot.label[i18n.language] });
      }

      if (pivot.mappings?.some(mapping => !mapping.key)) {
        return t('route.dossiers.manager.validation.error.pivots.key', { label: pivot.label[i18n.language] });
      }

      if (pivot.mappings?.some(mapping => !mapping.field || (mapping.field === 'custom' && !mapping.custom_value))) {
        return t('route.dossiers.manager.validation.error.pivots.field', { label: pivot.label[i18n.language] });
      }
    }

    return null;
  }, [dossier, i18n.language, searchDirty, searchTotal, t]);

  const save = useCallback(async () => {
    setLoading(true);

    try {
      if (!params.id) {
        const result = await dispatchApi(api.dossier.post(dossier));

        showSuccessMessage(t('route.dossiers.manager.create.success'));
        navigate(`/dossiers/${result.dossier_id}/edit`);
      } else {
        // Construct a clean payload with ONLY permitted fields
        // This solves the "Only type, title, owner, query, leads, pivots can be updated" error
        const updatePayload = {
          title: dossier.title,
          query: dossier.query,
          leads: dossier.leads,
          pivots: dossier.pivots,
          type: dossier.type,
          owner: dossier.owner
        };

        const updated = await dispatchApi(api.dossier.put(dossier.dossier_id, updatePayload));
        setDossier(updated);
        showSuccessMessage(t('route.dossiers.manager.edit.success'));
      }
    } finally {
      setLoading(false);
    }
  }, [dispatchApi, dossier, navigate, params.id, showSuccessMessage, t]);

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
  }, [setSearchParams, tab]);

  return (
    <PageCenter maxWidth="1000px" width="100%" textAlign="left" height="97%">
      <Box position="relative" height="100%">
        <Tooltip title={validationError}>
          <span>
            <Fab
              variant="extended"
              size="large"
              color="primary"
              disabled={!dirty || !!validationError || loading}
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
          </span>
        </Tooltip>
        <Stack spacing={1} height="100%">
          <Paper sx={{ p: 1 }}>
            <Stack spacing={1}>
              <Stack spacing={1} direction="row" alignItems="center">
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

                {dossier.dossier_id && canManageMembership && (
                  <Tooltip title={t('members')}>
                    <IconButton onClick={() => setMemberModalOpen(true)} disabled={loading}>
                      <PersonAdd />
                    </IconButton>
                  </Tooltip>
                )}
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

      {dossier.dossier_id && (
        <MembershipManagement
          open={memberModalOpen}
          onClose={() => setMemberModalOpen(false)}
          entityId={dossier.dossier_id}
          entityType="dossier"
        />
      )}
    </PageCenter>
  );
};

export default memo(DossierEditor);
