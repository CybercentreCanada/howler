import { Clear, Code, Comment, DataObject, History, LinkSharp, OpenInNew, QueryStats } from '@mui/icons-material';
import { Badge, Box, Divider, IconButton, Skeleton, Stack, Tab, Tabs, Tooltip, useTheme } from '@mui/material';
import TuiIconButton from 'components/elements/addons/buttons/CustomIconButton';

import { Icon } from '@iconify/react';
import useMatchers from 'components/app/hooks/useMatchers';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import { RecordContext } from 'components/app/providers/RecordProvider';
import { SocketContext } from 'components/app/providers/SocketProvider';
import FlexOne from 'components/elements/addons/layout/FlexOne';
import VSBox from 'components/elements/addons/layout/vsbox/VSBox';
import VSBoxContent from 'components/elements/addons/layout/vsbox/VSBoxContent';
import VSBoxHeader from 'components/elements/addons/layout/vsbox/VSBoxHeader';
import Phrase from 'components/elements/addons/search/phrase/Phrase';
import SocketBadge from 'components/elements/display/icons/SocketBadge';
import JSONViewer from 'components/elements/display/json/JSONViewer';
import HitActions from 'components/elements/hit/HitActions';
import HitBanner from 'components/elements/hit/HitBanner';
import HitLabels from 'components/elements/hit/HitLabels';
import { HitLayout } from 'components/elements/hit/HitLayout';
import HitLinks from 'components/elements/hit/HitLinks';
import HitOutline from 'components/elements/hit/HitOutline';
import HitOverview from 'components/elements/hit/HitOverview';
import HitSummary from 'components/elements/hit/HitSummary';
import ObjectDetails from 'components/elements/ObjectDetails';
import RecordComments from 'components/elements/record/RecordComments';
import RecordRelated from 'components/elements/record/RecordRelated';
import RecordWorklog from 'components/elements/record/RecordWorklog';
import useMyUserList from 'components/hooks/useMyUserList';
import ErrorBoundary from 'components/routes/ErrorBoundary';
import type { Analytic } from 'models/entities/generated/Analytic';
import type { Dossier } from 'models/entities/generated/Dossier';
import howlerPluginStore from 'plugins/store';
import type { FC } from 'react';
import { useContext, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { usePluginStore } from 'react-pluggable';
import { useLocation } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import { getUserList } from 'utils/hitFunctions';
import { validateRegex } from 'utils/stringUtils';
import { isHit } from 'utils/typeUtils';
import { tryParse } from 'utils/utils';
import LeadRenderer from '../view/LeadRenderer';

const InformationPane: FC<{ selected?: string; onClose?: () => void }> = ({ onClose, selected: _selected }) => {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const location = useLocation();
  const { emit, isOpen } = useContext(SocketContext);
  const { getMatchingOverview, getMatchingDossiers, getMatchingAnalytic } = useMatchers();
  const selected = useContextSelector(ParameterContext, ctx => ctx?.selected) ?? _selected;
  const pluginStore = usePluginStore();

  const getRecord = useContextSelector(RecordContext, ctx => ctx.getRecord);

  const [userIds, setUserIds] = useState<Set<string>>(new Set());
  const [analytic, setAnalytic] = useState<Analytic>();
  const [hasOverview, setHasOverview] = useState(false);
  const [tab, setTab] = useState<string>('overview');
  const [loading, setLoading] = useState<boolean>(false);
  const [filter, setFilter] = useState('');

  // In order to properly check for dossiers, we split dossiers into two
  const [_dossiers, setDossiers] = useState<Dossier[] | null>(null);
  const dossiers: Dossier[] = useMemo(() => _dossiers ?? [], [_dossiers]);

  const users = useMyUserList(userIds);

  const record = useContextSelector(RecordContext, ctx => ctx.records[selected]);

  howlerPluginStore.plugins.forEach(plugin => {
    pluginStore.executeFunction(`${plugin}.on`, 'viewing');
  });

  useEffect(() => {
    if (!selected) {
      return;
    }

    if (!record?.howler.data) {
      setLoading(true);
      getRecord(selected, true).finally(() => setLoading(false));
      return;
    }

    setUserIds(getUserList(record));

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [getRecord, selected]);

  useEffect(() => {
    if (selected) {
      setAnalytic(null);
      setDossiers(null);
      setHasOverview(false);
    }
  }, [selected]);

  useEffect(() => {
    if (isHit(record) && !analytic) {
      getMatchingAnalytic(record).then(setAnalytic);
    }
  }, [analytic, getMatchingAnalytic, record]);

  useEffect(() => {
    if (isHit(record) && !_dossiers) {
      getMatchingDossiers(record).then(setDossiers);
    }
  }, [_dossiers, getMatchingDossiers, record]);

  useEffect(() => {
    if (isHit(record)) {
      getMatchingOverview(record).then(_overview => setHasOverview(!!_overview));
    }
  }, [getMatchingOverview, record]);

  useEffect(() => {
    if (selected && isOpen()) {
      emit({
        broadcast: false,
        action: 'viewing',
        id: selected
      });

      return () =>
        emit({
          broadcast: false,
          action: 'stop_viewing',
          id: selected
        });
    }
  }, [emit, selected, isOpen]);

  useEffect(() => {
    if (hasOverview && tab === 'details') {
      setTab('overview');
    } else if (!hasOverview && tab === 'overview') {
      setTab('details');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasOverview]);

  const tabContent = useMemo(() => {
    if (!tab) {
      return;
    }

    const defaultContent = {
      details: () => <ObjectDetails obj={record} />,
      comments: () => <RecordComments record={record} users={users} />,
      raw: () => <JSONViewer data={!loading && record} hideSearch filter={filter} />,
      data: () => (
        <JSONViewer
          data={!loading && record?.howler?.data?.map(entry => tryParse(entry))}
          collapse={false}
          hideSearch
          filter={filter}
        />
      ),
      related: () => <RecordRelated record={record} />,
      worklog: () => <RecordWorklog record={!loading && record} users={users} />
    };

    if (!isHit(record)) {
      return defaultContent[tab]?.();
    }

    return {
      ...defaultContent,
      overview: () => <HitOverview hit={record} />,
      hit_aggregate: () => <HitSummary />,
      ...Object.fromEntries(
        (record?.howler.dossier ?? []).map((lead, index) => [
          'lead:' + index,
          () => <LeadRenderer lead={lead} hit={record} />
        ])
      ),
      ...Object.fromEntries(
        dossiers.flatMap((_dossier, dossierIndex) =>
          (_dossier.leads ?? []).map((_lead, leadIndex) => [
            `external-lead:${dossierIndex}:${leadIndex}`,
            () => <LeadRenderer lead={_lead} hit={record} />
          ])
        )
      )
    }[tab]?.();
  }, [dossiers, filter, record, loading, tab, users]);

  const hasError = useMemo(() => !validateRegex(filter), [filter]);

  return (
    <VSBox top={10} sx={{ height: '100%', flex: 1 }}>
      <Stack direction="column" flex={1} sx={{ overflowY: 'auto', flexGrow: 1 }} position="relative" spacing={1} ml={2}>
        <Stack direction="row" alignItems="center" spacing={0.5} flexShrink={0} pr={2}>
          <FlexOne />
          {onClose && !location.pathname.startsWith('/bundles') && (
            <TuiIconButton size="small" onClick={onClose} tooltip={t('hit.panel.details.exit')}>
              <Clear />
            </TuiIconButton>
          )}
          <SocketBadge size="small" />
          {analytic && (
            <TuiIconButton
              size="small"
              tooltip={t('hit.panel.analytic.open')}
              disabled={!analytic || loading}
              route={`/analytics/${analytic.analytic_id}`}
            >
              <QueryStats />
            </TuiIconButton>
          )}
          {!!record && (
            <TuiIconButton
              tooltip={t(`${record.__index}.open`)}
              href={`/${record.__index}s/${selected}`}
              disabled={!record || loading}
              size="small"
              target="_blank"
            >
              <OpenInNew />
            </TuiIconButton>
          )}
        </Stack>
        {isHit(record) && (
          <>
            <Box pr={2}>
              <HitBanner layout={HitLayout.DENSE} hit={record} />
            </Box>
            {!loading && (
              <>
                <HitOutline hit={record} layout={HitLayout.DENSE} forceAllFields />
                <HitLabels hit={record} />
              </>
            )}
            <HitLinks hit={record} analytic={analytic} dossiers={dossiers} />
          </>
        )}
        {loading && (
          <>
            <Skeleton variant="rounded" height={152} />
            <Skeleton height={124} />
          </>
        )}
        <VSBoxHeader ml={-1} mr={-1} pb={1} sx={{ top: '0px' }}>
          <Tabs
            value={tab === 'overview' && !hasOverview ? 'details' : tab}
            sx={{
              display: 'flex',
              flexDirection: 'row',
              pr: 2,
              alignItems: 'center',
              position: 'relative',
              '& > .MuiTabScrollButton-root': {
                position: 'absolute',
                top: 0,
                bottom: 0,
                zIndex: 5,
                backgroundColor: theme.palette.background.paper,
                '&:not(.Mui-disabled)': {
                  opacity: 1
                },
                '&:first-of-type': {
                  left: 0
                },
                '&:last-of-type': {
                  right: 0
                }
              }
            }}
            variant="scrollable"
          >
            <Tab
              sx={{ px: 2, minWidth: 0 }}
              label={
                <Tooltip title={t('viewer.comments')}>
                  <Badge
                    sx={{
                      '& > .MuiBadge-badge': {
                        backgroundColor: theme.palette.divider,
                        zIndex: 1,
                        right: theme.spacing(-0.5)
                      },
                      '& > svg': { zIndex: 2 }
                    }}
                    badgeContent={record?.howler.comment?.length ?? 0}
                  >
                    <Comment />
                  </Badge>
                </Tooltip>
              }
              value="comments"
              onClick={() => setTab('comments')}
            />
            {isHit(record) && hasOverview && (
              <Tab label={t('hit.viewer.overview')} value="overview" onClick={() => setTab('overview')} />
            )}
            <Tab label={t('hit.viewer.details')} value="details" onClick={() => setTab('details')} />
            {isHit(record) &&
              record?.howler.dossier?.map((lead, index) => (
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
              (_dossier.leads ?? []).map((_lead, leadIndex) => (
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
              value="data"
              onClick={() => setTab('data')}
              disabled={!record?.howler?.data}
            />
            <Tab
              sx={{ px: 2, minWidth: 0 }}
              label={
                <Tooltip title={t('hit.viewer.json')}>
                  <Code />
                </Tooltip>
              }
              value="raw"
              onClick={() => setTab('raw')}
            />
            <Tab
              sx={{ px: 2, minWidth: 0 }}
              label={
                <Tooltip title={t('hit.viewer.worklog')}>
                  <History />
                </Tooltip>
              }
              value="worklog"
              onClick={() => setTab('worklog')}
            />
            <Tab
              sx={{ px: 2, minWidth: 0 }}
              label={
                <Tooltip title={t('hit.viewer.related')}>
                  <LinkSharp />
                </Tooltip>
              }
              value="related"
              onClick={() => setTab('related')}
            />
          </Tabs>
          {['raw', 'data'].includes(tab) && (
            <Phrase
              sx={{ mt: 1, pr: 1 }}
              value={filter}
              onChange={setFilter}
              error={hasError}
              label={t('json.viewer.search.label')}
              placeholder={t('json.viewer.search.prompt')}
              endAdornment={
                <IconButton onClick={() => setFilter('')}>
                  <Clear />
                </IconButton>
              }
            />
          )}
        </VSBoxHeader>
        <ErrorBoundary>
          <VSBoxContent mr={-1} ml={-1} height="100%">
            <Stack height="100%" flex={1}>
              {tabContent}
            </Stack>
          </VSBoxContent>
        </ErrorBoundary>
      </Stack>
      {isHit(record) && (
        <Box pr={2} bgcolor={theme.palette.background.default} position="relative">
          <Divider orientation="horizontal" />
          <HitActions hit={record} />
        </Box>
      )}
    </VSBox>
  );
};

export default InformationPane;
