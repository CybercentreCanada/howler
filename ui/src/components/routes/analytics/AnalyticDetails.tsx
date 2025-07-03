import { Check, Delete, Edit, OpenInNew, SsidChart } from '@mui/icons-material';
import {
  Autocomplete,
  CircularProgress,
  Divider,
  FormControl,
  Grid,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Skeleton,
  Stack,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
  useTheme
} from '@mui/material';
import api from 'api';
import { useAppUser } from 'commons/components/app/hooks';
import PageCenter from 'commons/components/pages/PageCenter';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { UserListContext } from 'components/app/providers/UserListProvider';
import UserList from 'components/elements/UserList';
import HowlerAvatar from 'components/elements/display/HowlerAvatar';
import useMyApi from 'components/hooks/useMyApi';
import useMySnackbar from 'components/hooks/useMySnackbar';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { Analytic } from 'models/entities/generated/Analytic';
import { useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { RULE_INTERVALS } from 'utils/constants';
import AnalyticComments from './AnalyticComments';
import AnalyticHitComments from './AnalyticHitComments';
import AnalyticNotebooks from './AnalyticNotebooks';
import AnalyticOverview from './AnalyticOverview';
import AnalyticOverviews from './AnalyticOverviews';
import AnalyticTemplates from './AnalyticTemplates';
import RuleView from './RuleView';
import TriageSettings from './TriageSettings';

const AnalyticDetails = () => {
  const { t } = useTranslation();
  const params = useParams();
  const navigate = useNavigate();
  const { user } = useAppUser<HowlerUser>();
  const [searchParams, setSearchParams] = useSearchParams();
  const { dispatchApi } = useMyApi();
  const theme = useTheme();
  const { showSuccessMessage } = useMySnackbar();
  const { users, searchUsers } = useContext(UserListContext);
  const { config } = useContext(ApiConfigContext);

  const [analytic, setAnalytic] = useState<Analytic>(null);
  const [tab, setTab] = useState(searchParams.get('tab') ?? 'overview');
  const [editingInterval, setEditingInterval] = useState(false);
  const [intervalLoading, setIntervalLoading] = useState(false);
  const [crontab, setCrontab] = useState(RULE_INTERVALS[3].crontab);

  const filteredContributors = useMemo(
    () => (analytic?.contributors ?? []).filter(_user => _user !== analytic?.owner),
    [analytic?.contributors, analytic?.owner]
  );

  useEffect(() => {
    dispatchApi(api.analytic.get(params.id) as Promise<Analytic>).then(setAnalytic);
  }, [dispatchApi, params.id]);

  const [filter, _setFilter] = useState<string | null>(searchParams.get('filter') ?? null);
  const setFilter = useCallback(
    (detection: string) => {
      if (filter === detection) {
        _setFilter(null);
      } else {
        _setFilter(detection);
      }
    },
    [filter]
  );

  const onOwnerChange = useCallback(
    async (ownerId: string) => {
      const result = await dispatchApi(api.analytic.owner.post(analytic.analytic_id, { username: ownerId }), {
        throwError: true,
        showError: true
      });

      setAnalytic(result);
    },
    [analytic?.analytic_id, dispatchApi]
  );

  const onDelete = useCallback(async () => {
    await dispatchApi(api.analytic.del(analytic?.analytic_id));

    showSuccessMessage(t('route.analytics.deleted'));
    navigate('/analytics');
  }, [analytic?.analytic_id, dispatchApi, navigate, showSuccessMessage, t]);

  const onEdit = useCallback(async () => {
    if (editingInterval) {
      setIntervalLoading(true);

      try {
        await dispatchApi(
          api.analytic.put(analytic?.analytic_id, {
            rule_crontab: crontab
          })
        );

        setAnalytic(_analytic => ({
          ..._analytic,
          rule_crontab: crontab
        }));

        setEditingInterval(false);
      } finally {
        setIntervalLoading(false);
      }
    } else {
      setEditingInterval(true);
    }
  }, [analytic?.analytic_id, crontab, dispatchApi, editingInterval]);

  useEffect(() => {
    if (searchParams.get('tab') !== tab) {
      searchParams.set('tab', tab);
    }

    if (searchParams.get('filter') !== filter) {
      if (filter) {
        searchParams.set('filter', filter);
      } else {
        searchParams.delete('filter');
      }
    }

    setSearchParams(searchParams, { replace: true });
  }, [filter, searchParams, setSearchParams, tab]);

  useEffect(() => {
    if (!analytic?.owner) {
      return;
    }

    searchUsers(`uname:"${analytic?.owner}"`);
  }, [analytic?.owner, searchUsers]);

  return (
    <PageCenter maxWidth="1500px" textAlign="left" height="100%">
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
        <Typography variant="h3" mb={2}>
          <Stack direction="row" spacing={1} alignItems="center">
            {analytic ? (
              <span>{analytic.name}</span>
            ) : (
              <Stack>
                <Skeleton variant="text" width="170px" height="28px" />
                <Skeleton variant="text" width="140px" height="28px" />
              </Stack>
            )}

            {analytic?.rule && (
              <>
                <Tooltip title={t('route.analytics.rule')}>
                  <SsidChart fontSize="large" color="info" />
                </Tooltip>
                {(analytic?.owner === user.username || user.roles.includes('admin')) && (
                  <IconButton onClick={onDelete}>
                    <Delete />
                  </IconButton>
                )}
              </>
            )}
            <IconButton component={Link} to={`/hits?query=howler.analytic:"${analytic?.name}"`}>
              <OpenInNew />
            </IconButton>
          </Stack>
        </Typography>
        <Stack
          direction="row"
          spacing={1}
          divider={
            <Divider
              flexItem
              orientation="vertical"
              sx={{ marginLeft: `${theme.spacing(2)} !important`, marginRight: `${theme.spacing(1)} !important` }}
            />
          }
          mb={2}
        >
          <Stack spacing={1} alignItems="start">
            <Typography variant="body1" color="text.secondary">
              {t('owner')}
            </Typography>
            <Stack direction="row" spacing={1} alignItems="center">
              {!analytic?.rule ? (
                <UserList
                  buttonSx={{
                    marginTop: '0 !important',
                    marginLeft: `${theme.spacing(-1)} !important`,
                    marginRight: `${theme.spacing(-1)} !important`
                  }}
                  userId={analytic?.owner}
                  onChange={onOwnerChange}
                  i18nLabel="route.analytics.set.owner"
                />
              ) : (
                <HowlerAvatar userId={analytic?.owner} />
              )}
              <Stack>
                {users[analytic?.owner] ? (
                  <>
                    <Typography variant="body1">{users[analytic?.owner].name}</Typography>
                    <Typography
                      component="a"
                      href={`mailto:${users[analytic?.owner].email}`}
                      variant="caption"
                      color="text.secondary"
                    >
                      {users[analytic?.owner].email}
                    </Typography>
                  </>
                ) : (
                  <>
                    <Skeleton variant="text" width="70px" />
                    <Skeleton variant="text" width="60px" />
                  </>
                )}
              </Stack>
            </Stack>
          </Stack>
          {filteredContributors.length > 0 && (
            <Stack spacing={1}>
              <Typography variant="body1" color="text.secondary">
                {t('route.analytics.contributors')}
              </Typography>
              <Stack direction="row" alignItems="center" spacing={1}>
                {filteredContributors.map(_user => (
                  <HowlerAvatar key={_user} userId={_user} />
                ))}
              </Stack>
            </Stack>
          )}
          {analytic?.rule_crontab && (
            <Stack direction="row" spacing={1}>
              <Stack spacing={1} justifyContent="space-between">
                <Typography variant="body1" color="text.secondary">
                  {t('rule.interval')}
                </Typography>
                {editingInterval ? (
                  <FormControl sx={{ minWidth: '200px' }}>
                    <InputLabel>{t('rule.interval')}</InputLabel>
                    <Select
                      size="small"
                      label={t('rule.interval')}
                      onChange={event => setCrontab(event.target.value)}
                      value={crontab}
                    >
                      {RULE_INTERVALS.map(interval => (
                        <MenuItem key={interval.key} value={interval.crontab}>
                          {t(interval.key)}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                ) : (
                  <code
                    style={{
                      backgroundColor: theme.palette.background.paper,
                      padding: theme.spacing(0.5),
                      alignSelf: 'start',
                      borderRadius: theme.shape.borderRadius,
                      border: `thin solid ${theme.palette.divider}`,
                      width: '100%'
                    }}
                  >
                    {analytic.rule_crontab}
                  </code>
                )}
              </Stack>
              {(analytic?.owner === user.username || user.roles.includes('admin')) && (
                <Tooltip title={editingInterval ? t('rule.interval.save') : t('rule.interval.edit')}>
                  <IconButton disabled={intervalLoading} sx={{ alignSelf: 'end' }} onClick={onEdit}>
                    {intervalLoading ? <CircularProgress size={20} /> : editingInterval ? <Check /> : <Edit />}
                  </IconButton>
                </Tooltip>
              )}
            </Stack>
          )}
        </Stack>
        <Grid container>
          <Grid item xs={12} md={9}>
            <Tabs value={tab} onChange={(_, _tab) => setTab(_tab)}>
              <Tab label={t('route.analytics.tab.overview')} value="overview" />
              <Tab label={t('route.analytics.tab.comments')} value="comments" />
              <Tab label={t('route.analytics.tab.hit_comments')} value="hit_comments" />
              <Tab label={t('route.analytics.tab.templates')} value="templates" />
              <Tab label={t('route.analytics.tab.overviews')} value="overviews" />
              {analytic?.rule && <Tab label={t('route.analytics.tab.rule')} value="rule" />}
              {config?.configuration.features.notebook && (
                <Tab label={t('route.analytics.tab.notebooks')} value="notebooks" />
              )}
              <Tab label={t('route.analytics.tab.triage')} value="triage" />
            </Tabs>
          </Grid>

          {['comments', 'hit_comments'].includes(tab) && (
            <Grid item xs={12} md={3}>
              <Autocomplete
                options={analytic?.detections ?? []}
                renderInput={param => <TextField {...param} label="Detection" />}
                value={filter}
                onChange={(_, v) => setFilter(v)}
              />
            </Grid>
          )}
        </Grid>
        {
          {
            comments: <AnalyticComments analytic={analytic} setAnalytic={setAnalytic} />,
            hit_comments: <AnalyticHitComments analytic={analytic} />,
            overview: <AnalyticOverview analytic={analytic} setAnalytic={setAnalytic} />,
            overviews: <AnalyticOverviews analytic={analytic} />,
            rule: <RuleView analytic={analytic} setAnalytic={setAnalytic} />,
            templates: <AnalyticTemplates analytic={analytic} />,
            triage: <TriageSettings analytic={analytic} setAnalytic={setAnalytic} />,
            ...(config?.configuration.features.notebook
              ? {
                  notebooks: <AnalyticNotebooks analytic={analytic} setAnalytic={setAnalytic} />
                }
              : {})
          }[tab]
        }
      </div>
    </PageCenter>
  );
};

export default AnalyticDetails;
