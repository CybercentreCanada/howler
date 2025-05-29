import { Icon } from '@iconify/react/dist/iconify.js';
import { Code, Comment, DataObject, History, LinkSharp, QueryStats, ViewAgenda } from '@mui/icons-material';
import {
  Badge,
  Box,
  CardContent,
  Collapse,
  IconButton,
  Skeleton,
  Stack,
  Tab,
  Tabs,
  Tooltip,
  useMediaQuery,
  useTheme
} from '@mui/material';
import PageCenter from 'commons/components/pages/PageCenter';
import { AnalyticContext } from 'components/app/providers/AnalyticProvider';
import { DossierContext } from 'components/app/providers/DossierProvider';
import { HitContext } from 'components/app/providers/HitProvider';
import { OverviewContext } from 'components/app/providers/OverviewProvider';
import { TemplateContext } from 'components/app/providers/TemplateProvider';
import FlexOne from 'components/elements/addons/layout/FlexOne';
import HowlerCard from 'components/elements/display/HowlerCard';
import BundleButton from 'components/elements/display/icons/BundleButton';
import SocketBadge from 'components/elements/display/icons/SocketBadge';
import JSONViewer from 'components/elements/display/json/JSONViewer';
import HitActions from 'components/elements/hit/HitActions';
import HitBanner from 'components/elements/hit/HitBanner';
import HitComments from 'components/elements/hit/HitComments';
import HitDetails from 'components/elements/hit/HitDetails';
import HitLabels from 'components/elements/hit/HitLabels';
import { HitLayout } from 'components/elements/hit/HitLayout';
import HitNotebooks from 'components/elements/hit/HitNotebooks';
import HitOutline from 'components/elements/hit/HitOutline';
import HitOverview from 'components/elements/hit/HitOverview';
import HitRelated from 'components/elements/hit/HitRelated';
import HitWorklog from 'components/elements/hit/HitWorklog';
import PivotLink from 'components/elements/hit/related/PivotLink';
import RelatedLink from 'components/elements/hit/related/RelatedLink';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import useMyUserList from 'components/hooks/useMyUserList';
import uniqBy from 'lodash-es/uniqBy';
import type { Analytic } from 'models/entities/generated/Analytic';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { FC } from 'react';
import { useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import { StorageKey } from 'utils/constants';
import { getUserList } from 'utils/hitFunctions';
import { tryParse } from 'utils/utils';
import LeadRenderer from './LeadRenderer';

export enum Orientation {
  VERTICAL = 'vertical',
  HORIZONTAL = 'horizontal'
}

const HitViewer: FC = () => {
  const { t, i18n } = useTranslation();
  const params = useParams();
  const navigate = useNavigate();
  const theme = useTheme();
  const isUnderLg = useMediaQuery(theme.breakpoints.down('lg'));
  const [orientation, setOrientation] = useMyLocalStorageItem(StorageKey.VIEWER_ORIENTATION, Orientation.VERTICAL);
  const refreshTemplates = useContextSelector(TemplateContext, ctx => ctx.refresh);
  const { getAnalyticFromName } = useContext(AnalyticContext);
  const { getMatchingOverview, refresh: refreshOverviews } = useContext(OverviewContext);
  const getMatchingDossiers = useContextSelector(DossierContext, ctx => ctx.getMatchingDossiers);

  const getHit = useContextSelector(HitContext, ctx => ctx.getHit);
  const hit = useContextSelector(HitContext, ctx => ctx.hits[params.id]);

  const [userIds, setUserIds] = useState<Set<string>>(new Set());
  const users = useMyUserList(userIds);
  const [tab, setTab] = useState<string>('details');
  const [analytic, setAnalytic] = useState<Analytic>();
  const [dossiers, setDossiers] = useState<Dossier[]>([]);

  const fetchData = useCallback(async () => {
    try {
      let existingHit = hit;
      if (!existingHit) {
        existingHit = await getHit(params.id, true);
      }
      setUserIds(getUserList(existingHit));

      setAnalytic(await getAnalyticFromName(existingHit.howler.analytic));
    } catch (err) {
      if (err.cause?.api_status_code === 404) {
        navigate('/404');
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [getAnalyticFromName, getHit, params.id, navigate]);

  useEffect(() => {
    if (isUnderLg) {
      setOrientation(Orientation.HORIZONTAL);
    }
  }, [isUnderLg, setOrientation]);

  useEffect(() => {
    fetchData();
  }, [params.id, fetchData]);

  const onOrientationChange = useCallback(
    () => setOrientation(orientation === Orientation.VERTICAL ? Orientation.HORIZONTAL : Orientation.VERTICAL),
    [orientation, setOrientation]
  );

  const matchingOverview = useMemo(() => getMatchingOverview(hit), [getMatchingOverview, hit]);

  useEffect(() => {
    refreshTemplates();
    refreshOverviews();
  }, [refreshOverviews, refreshTemplates]);

  useEffect(() => {
    if (matchingOverview && tab === 'details') {
      setTab('overview');
    } else if (!matchingOverview && tab === 'overview') {
      setTab('details');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matchingOverview]);

  const tabContent = useMemo(() => {
    if (!tab || !hit) {
      return;
    }

    return {
      overview: () => <HitOverview hit={hit} />,
      details: () => <HitDetails hit={hit} />,
      hit_comments: () => <HitComments hit={hit} users={users} />,
      hit_raw: () => <JSONViewer data={hit} />,
      hit_data: () => <JSONViewer data={hit?.howler?.data?.map(entry => tryParse(entry))} collapse={false} />,
      hit_worklog: () => <HitWorklog hit={hit} users={users} />,
      hit_related: () => <HitRelated hit={hit} />,
      ...Object.fromEntries(
        hit?.howler.dossier?.map((lead, index) => ['lead:' + index, () => <LeadRenderer lead={lead} />]) ?? []
      ),
      ...Object.fromEntries(
        dossiers.flatMap((_dossier, dossierIndex) =>
          _dossier.leads?.map((_lead, leadIndex) => [
            `external-lead:${dossierIndex}:${leadIndex}`,
            () => <LeadRenderer lead={_lead} hit={hit} />
          ])
        )
      )
    }[tab]?.();
  }, [dossiers, hit, tab, users]);

  useEffect(() => {
    if (!hit) {
      return;
    }

    getMatchingDossiers(hit.howler.id).then(setDossiers);
  }, [getMatchingDossiers, hit]);

  if (!hit) {
    return (
      <PageCenter>
        <Skeleton variant="rounded" height="520px" />
      </PageCenter>
    );
  }

  return (
    <PageCenter maxWidth="1500px">
      <Box
        sx={{
          display: 'grid',
          position: 'relative',
          gridTemplateColumns: `1fr ${orientation === 'vertical' ? '300px' : '0px'}`,
          alignItems: 'stretch',
          gap: theme.spacing(2),
          transition: `${theme.transitions.duration.standard}ms`,
          mb: 1
        }}
        textAlign="left"
      >
        <Collapse
          sx={{ gridColumn: '1 / span 2', '& [class*=MuiStack-root]': { padding: '0 !important' } }}
          in={orientation === 'horizontal'}
        >
          <HitActions hit={hit} orientation="horizontal" />
        </Collapse>
        <Box
          sx={{
            display: 'flex',
            '& > .MuiPaper-root': { flex: 1 },
            mr: orientation === 'vertical' ? 0 : -2
          }}
        >
          <HowlerCard tabIndex={0} sx={{ position: 'relative' }}>
            <CardContent>
              <HitBanner hit={hit} layout={HitLayout.COMFY} useListener />
              <HitOutline hit={hit} layout={HitLayout.COMFY} />
              <HitLabels hit={hit} />
              {(hit?.howler?.links?.length > 0 ||
                analytic?.notebooks?.length > 0 ||
                dossiers.filter(_dossier => _dossier.pivots?.length > 0).length > 0) && (
                <Stack direction="row" spacing={1} pr={2}>
                  {analytic?.notebooks?.length > 0 && <HitNotebooks analytic={analytic} hit={hit} />}
                  {hit?.howler?.links?.length > 0 &&
                    uniqBy(hit.howler.links, 'href')
                      .slice(0, 3)
                      .map(l => <RelatedLink key={l.href} compact {...l} />)}
                  {dossiers.flatMap(_dossier =>
                    (_dossier.pivots ?? []).map((_pivot, index) => (
                      // eslint-disable-next-line react/no-array-index-key
                      <PivotLink key={_dossier.dossier_id + index} pivot={_pivot} hit={hit} compact />
                    ))
                  )}
                </Stack>
              )}
            </CardContent>
          </HowlerCard>
          {!isUnderLg && (
            <Stack
              spacing={1}
              sx={{
                position: 'absolute',
                top: theme.spacing(2),
                right: theme.spacing(-6)
              }}
            >
              <Tooltip title={t('page.hits.view.layout')}>
                <IconButton onClick={onOrientationChange}>
                  <ViewAgenda
                    sx={{ transition: 'rotate 250ms', rotate: orientation === 'vertical' ? '90deg' : '0deg' }}
                  />
                </IconButton>
              </Tooltip>
              <SocketBadge size="medium" />
              {analytic && (
                <Tooltip title={t('hit.panel.analytic.open')}>
                  <IconButton onClick={() => navigate(`/analytics/${analytic.analytic_id}`)}>
                    <QueryStats />
                  </IconButton>
                </Tooltip>
              )}
              {hit?.howler.bundles?.length > 0 && <BundleButton ids={hit.howler.bundles} />}
            </Stack>
          )}
        </Box>
        <HowlerCard sx={[orientation === 'horizontal' && { height: '0px' }]}>
          <CardContent sx={{ padding: 1, position: 'relative' }}>
            <HitActions hit={hit} orientation="vertical" />
          </CardContent>
        </HowlerCard>
        <Box sx={{ gridColumn: '1 / span 2', mb: 1 }}>
          <Tabs
            value={tab === 'overview' && !matchingOverview ? 'details' : tab}
            sx={{ display: 'flex', flexDirection: 'row', pr: 2, alignItems: 'center' }}
          >
            {hit?.howler?.is_bundle && (
              <Tab label={t('hit.viewer.aggregate')} value="hit_aggregate" onClick={() => setTab('hit_aggregate')} />
            )}
            {matchingOverview && (
              <Tab label={t('hit.viewer.overview')} value="overview" onClick={() => setTab('overview')} />
            )}
            <Tab label={t('hit.viewer.details')} value="details" onClick={() => setTab('details')} />
            {hit?.howler.dossier?.map((lead, index) => (
              <Tab
                // eslint-disable-next-line react/no-array-index-key
                key={'lead:' + index}
                label={
                  <Stack direction="row" spacing={0.5}>
                    {lead.icon && <Icon icon={lead.icon} />}
                    <span>{i18n.language === 'en' ? lead.label.en : lead.label.fr}</span>
                  </Stack>
                }
                value={'lead:' + index}
                onClick={() => setTab('lead:' + index)}
              />
            ))}

            {dossiers.flatMap((_dossier, dossierIndex) =>
              _dossier.leads?.map((_lead, leadIndex) => (
                <Tab
                  // eslint-disable-next-line react/no-array-index-key
                  key={`external-lead:${dossierIndex}:${leadIndex}`}
                  label={
                    <Stack direction="row" spacing={0.5}>
                      {_lead.icon && <Icon icon={_lead.icon} />}
                      <span>{i18n.language === 'en' ? _lead.label.en : _lead.label.fr}</span>
                    </Stack>
                  }
                  value={`external-lead:${dossierIndex}:${leadIndex}`}
                  onClick={() => setTab(`external-lead:${dossierIndex}:${leadIndex}`)}
                />
              ))
            )}
            <FlexOne />
            <Tab
              sx={{ px: 2, minWidth: 0 }}
              label={
                <Tooltip title={t('hit.viewer.data')}>
                  <DataObject />
                </Tooltip>
              }
              value="hit_data"
              onClick={() => setTab('hit_data')}
              disabled={!hit?.howler?.data}
            />
            <Tab
              sx={{ px: 2, minWidth: 0 }}
              label={
                <Tooltip title={t('hit.viewer.json')}>
                  <Code />
                </Tooltip>
              }
              value="hit_raw"
              onClick={() => setTab('hit_raw')}
            />
            <Tab
              sx={{ px: 2, minWidth: 0 }}
              label={
                <Tooltip title={t('hit.viewer.comments')}>
                  <Badge
                    sx={{
                      '& > .MuiBadge-badge': {
                        backgroundColor: theme.palette.divider,
                        zIndex: 1,
                        right: theme.spacing(-0.5)
                      },
                      '& > svg': { zIndex: 2 }
                    }}
                    badgeContent={hit?.howler.comment?.length ?? 0}
                  >
                    <Comment />
                  </Badge>
                </Tooltip>
              }
              value="hit_comments"
              onClick={() => setTab('hit_comments')}
            />
            <Tab
              sx={{ px: 2, minWidth: 0 }}
              label={
                <Tooltip title={t('hit.viewer.worklog')}>
                  <History />
                </Tooltip>
              }
              value="hit_worklog"
              onClick={() => setTab('hit_worklog')}
            />
            <Tab
              sx={{ px: 2, minWidth: 0 }}
              label={
                <Tooltip title={t('hit.viewer.related')}>
                  <LinkSharp />
                </Tooltip>
              }
              value="hit_related"
              onClick={() => setTab('hit_related')}
            />
          </Tabs>
        </Box>
        <Box
          sx={{
            gridColumn: '1 / span 2',
            '& > div': { padding: 0 },
            '& .react-json-view': { backgroundColor: 'transparent !important' }
          }}
        >
          {tabContent}
        </Box>
      </Box>
    </PageCenter>
  );
};

export default HitViewer;
