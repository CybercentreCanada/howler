import { ExpandMore, Refresh } from '@mui/icons-material';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  LinearProgress,
  Stack,
  Typography
} from '@mui/material';
import api, { type HowlerResponse } from 'api';
import type { RecievedDataType } from 'components/app/providers/SocketProvider';
import { SocketContext } from 'components/app/providers/SocketProvider';
import useMyApi from 'components/hooks/useMyApi';
import useMyLocalStorage from 'components/hooks/useMyLocalStorage';
import type { ActionRun, ActionRunCounts, ActionRunState, ActionRunSummary } from 'models/ActionRunTypes';
import { useCallback, useContext, useEffect, useId, useRef, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { StorageKey } from 'utils/constants';

type ActionRunEvent = { operation_id: string; run_id: string; request_id: string };
type ActionRunHistoryProps = { actionId?: string; requestId?: string; contextId?: string; acceptedRunIds?: string[] };

const ACTIVE_STATES: ActionRunState[] = ['queued', 'running'];
const EMPTY_ACCEPTED_RUN_IDS: string[] = [];

const ActionRunHistory: FC<ActionRunHistoryProps> = props => {
  const { get } = useMyLocalStorage();
  const authSessionKey = get<string>(StorageKey.APP_TOKEN) ?? '';
  const acceptedRunIds = props.acceptedRunIds ?? EMPTY_ACCEPTED_RUN_IDS;
  const sessionKey = JSON.stringify([
    authSessionKey,
    props.actionId ?? null,
    props.requestId ?? null,
    props.contextId ?? null
  ]);
  return <ActionRunHistorySession key={sessionKey} {...props} acceptedRunIds={acceptedRunIds} />;
};

const getApiStatusCode = (error: unknown) =>
  error instanceof Error ? (error.cause as HowlerResponse<unknown> | undefined)?.api_status_code : undefined;
const isUnavailable = (statusCode?: number) => statusCode === 401 || statusCode === 403 || statusCode === 404;

const ActionRunHistorySession: FC<ActionRunHistoryProps & { acceptedRunIds: string[] }> = ({
  actionId,
  requestId,
  acceptedRunIds
}) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const { addListener, removeListener } = useContext(SocketContext);
  const listenerKey = `ai-triage-runs-${useId()}`;
  const [items, setItems] = useState<ActionRunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [nextOffset, setNextOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<string>();
  const [selectedRun, setSelectedRun] = useState<ActionRun>();
  const [detailLoading, setDetailLoading] = useState(false);
  const [dismissedRunIds, setDismissedRunIds] = useState<Set<string>>(() => new Set());
  const dismissedRunIdsRef = useRef(new Set<string>());
  const listSequence = useRef(0);
  const detailSequence = useRef(0);
  const selectedRunIdRef = useRef<string | undefined>(undefined);
  const hasLoaded = useRef(false);
  const acceptedRunKey = JSON.stringify(acceptedRunIds);
  const acceptedRunIdsRef = useRef(acceptedRunIds);

  const dismissRunIds = useCallback((runIds: string[]) => {
    const newIds = runIds.filter(runId => !dismissedRunIdsRef.current.has(runId));
    if (newIds.length === 0) {
      return;
    }
    const next = new Set([...dismissedRunIdsRef.current, ...newIds]);
    dismissedRunIdsRef.current = next;
    setDismissedRunIds(next);
  }, []);

  const clearHistory = useCallback(() => {
    listSequence.current += 1;
    detailSequence.current += 1;
    selectedRunIdRef.current = undefined;
    setItems([]);
    setNextOffset(0);
    setHasMore(false);
    setSelectedRun(undefined);
    setSelectedRunId(undefined);
    setLoading(false);
    setRefreshing(false);
    setLoadingMore(false);
    setDetailLoading(false);
    dismissRunIds(acceptedRunIdsRef.current);
  }, [dismissRunIds]);

  const fetchList = useCallback(
    async (offset: number, append: boolean, quiet: boolean) => {
      const sequence = ++listSequence.current;
      if (offset > 0) {
        setLoadingMore(true);
      } else if (quiet) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      try {
        const response = await dispatchApi(
          api.action.runs.list({
            operation_id: 'ai_triage',
            action_id: actionId,
            request_id: requestId,
            offset,
            rows: 20
          }),
          { throwError: true, showError: false }
        );
        if (sequence !== listSequence.current) {
          return;
        }
        if (!response) {
          clearHistory();
          return;
        }

        const incoming = response.items.filter(item => !dismissedRunIdsRef.current.has(item.run_id));
        setItems(current => {
          if (append) {
            const updates = new Map(incoming.map(item => [item.run_id, item]));
            const existingIds = new Set(current.map(item => item.run_id));
            return [
              ...current.map(item => updates.get(item.run_id) ?? item),
              ...incoming.filter(item => !existingIds.has(item.run_id))
            ];
          }
          return quiet
            ? [...incoming, ...current.filter(item => !incoming.some(next => next.run_id === item.run_id))]
            : incoming;
        });
        setNextOffset(current =>
          quiet ? Math.max(current, response.offset + response.rows) : response.offset + response.rows
        );
        setHasMore(response.has_more);
      } catch (error) {
        if (sequence === listSequence.current && isUnavailable(getApiStatusCode(error))) {
          clearHistory();
        }
      } finally {
        if (sequence === listSequence.current) {
          setLoading(false);
          setRefreshing(false);
          setLoadingMore(false);
        }
      }
    },
    [actionId, clearHistory, dispatchApi, requestId]
  );

  const refreshList = useCallback((quiet = false) => fetchList(0, false, quiet), [fetchList]);
  const loadMore = useCallback(
    () => hasMore && !loadingMore && fetchList(nextOffset, true, false),
    [fetchList, hasMore, loadingMore, nextOffset]
  );

  const fetchRun = useCallback(
    async (runId: string) => {
      const sequence = ++detailSequence.current;
      setDetailLoading(true);
      try {
        const result = await dispatchApi(api.action.runs.get(runId), { throwError: true, showError: false });
        if (sequence !== detailSequence.current || selectedRunIdRef.current !== runId) {
          return;
        }
        if (!result) {
          clearHistory();
          return;
        }
        setSelectedRun(result);
        setItems(current => current.map(item => (item.run_id === runId ? result : item)));
      } catch (error) {
        if (sequence !== detailSequence.current || selectedRunIdRef.current !== runId) {
          return;
        }
        const statusCode = getApiStatusCode(error);
        if (statusCode === 401) {
          clearHistory();
        } else if (statusCode === 403 || statusCode === 404) {
          listSequence.current += 1;
          selectedRunIdRef.current = undefined;
          dismissRunIds([runId]);
          setItems(current => current.filter(item => item.run_id !== runId));
          setSelectedRun(undefined);
          setSelectedRunId(undefined);
          setRefreshing(false);
          setLoadingMore(false);
        }
      } finally {
        if (sequence === detailSequence.current) {
          setDetailLoading(false);
        }
      }
    },
    [clearHistory, dismissRunIds, dispatchApi]
  );

  const pendingAcceptedIds = acceptedRunIds.filter(
    runId => !items.some(item => item.run_id === runId) && !dismissedRunIds.has(runId)
  );
  const handleActionEvent = useCallback(
    (data: RecievedDataType<ActionRunEvent>) => {
      if (
        data.type !== 'action' ||
        data.operation_id !== 'ai_triage' ||
        !data.run_id ||
        (requestId && data.request_id !== requestId)
      ) {
        return;
      }
      void refreshList(true);
      if (selectedRunIdRef.current === data.run_id) {
        void fetchRun(data.run_id);
      }
    },
    [fetchRun, refreshList, requestId]
  );

  useEffect(() => {
    acceptedRunIdsRef.current = acceptedRunIds;
  }, [acceptedRunKey, acceptedRunIds]);

  useEffect(() => {
    const quiet = hasLoaded.current;
    hasLoaded.current = true;
    void refreshList(quiet);
  }, [acceptedRunKey, refreshList]);

  useEffect(
    () => () => {
      listSequence.current += 1;
      detailSequence.current += 1;
    },
    []
  );

  useEffect(() => {
    addListener<ActionRunEvent>(listenerKey, handleActionEvent);
    return () => removeListener(listenerKey);
  }, [addListener, handleActionEvent, listenerKey, removeListener]);

  const hasActiveRuns =
    items.some(item => ACTIVE_STATES.includes(item.state)) ||
    (selectedRun ? ACTIVE_STATES.includes(selectedRun.state) : false) ||
    pendingAcceptedIds.length > 0;
  useEffect(() => {
    if (!hasActiveRuns) {
      return;
    }
    const interval = window.setInterval(() => {
      void refreshList(true);
      const selectedItem = items.find(item => item.run_id === selectedRunIdRef.current);
      if (
        selectedRunIdRef.current &&
        (selectedRun
          ? ACTIVE_STATES.includes(selectedRun.state)
          : selectedItem && ACTIVE_STATES.includes(selectedItem.state))
      ) {
        void fetchRun(selectedRunIdRef.current);
      }
    }, 3000);
    return () => window.clearInterval(interval);
  }, [fetchRun, hasActiveRuns, items, refreshList, selectedRun]);

  const selectRun = (runId: string) => {
    if (selectedRunIdRef.current === runId) {
      selectedRunIdRef.current = undefined;
      detailSequence.current += 1;
      setSelectedRunId(undefined);
      setSelectedRun(undefined);
      setDetailLoading(false);
      return;
    }
    selectedRunIdRef.current = runId;
    setSelectedRunId(runId);
    setSelectedRun(undefined);
    void fetchRun(runId);
  };
  const countLabel = (counts: ActionRunCounts) =>
    `${t('route.actions.run.count.total', { count: counts.total })} · ${t('route.actions.run.count.queued', { count: counts.queued })} · ${t('route.actions.run.count.running', { count: counts.running })} · ${t('route.actions.run.count.succeeded', { count: counts.succeeded })} · ${t('route.actions.run.count.failed', { count: counts.failed })} · ${t('route.actions.run.count.skipped', { count: counts.skipped })}`;

  return (
    <Stack spacing={1}>
      <Stack direction="row" alignItems="center" justifyContent="space-between">
        <Typography variant="h6">{t('route.actions.run.history')}</Typography>
        <IconButton
          aria-label={t('route.actions.run.refresh')}
          size="small"
          disabled={refreshing}
          onClick={() => void refreshList(true)}
        >
          {refreshing ? <CircularProgress size={18} /> : <Refresh fontSize="small" />}
        </IconButton>
      </Stack>
      {pendingAcceptedIds.length > 0 && (
        <Alert severity="info" variant="outlined">
          <Stack spacing={0.5}>
            <Typography>{t('route.actions.run.accepted.pending')}</Typography>
            {pendingAcceptedIds.map(runId => (
              <Typography key={runId} variant="caption">
                {t('route.actions.run.id', { runId })}
              </Typography>
            ))}
          </Stack>
        </Alert>
      )}
      {loading && items.length === 0 && <LinearProgress />}
      {!loading && items.length === 0 && <Typography color="text.secondary">{t('route.actions.run.empty')}</Typography>}
      {items.map(run => (
        <Accordion
          key={run.run_id}
          variant="outlined"
          expanded={selectedRunId === run.run_id}
          onChange={() => selectRun(run.run_id)}
        >
          <AccordionSummary expandIcon={<ExpandMore />}>
            <Stack spacing={0.5} sx={{ minWidth: 0 }}>
              <Stack direction="row" spacing={1} alignItems="center">
                <Typography>{t(`route.actions.run.state.${run.state}`)}</Typography>
                <Typography variant="caption" color="text.secondary" noWrap>
                  {run.run_id}
                </Typography>
              </Stack>
              <Typography variant="caption" color="text.secondary">
                {countLabel(run.counts)}
              </Typography>
            </Stack>
          </AccordionSummary>
          <AccordionDetails>
            {detailLoading && <LinearProgress />}
            {selectedRun?.run_id === run.run_id && <RunDetails run={selectedRun} />}
          </AccordionDetails>
        </Accordion>
      ))}
      {hasMore && (
        <Button size="small" disabled={loadingMore} onClick={() => void loadMore()}>
          {loadingMore ? <CircularProgress size={16} /> : t('route.actions.run.loadMore')}
        </Button>
      )}
    </Stack>
  );
};

const RunDetails: FC<{ run: ActionRun }> = ({ run }) => {
  const { t } = useTranslation();
  const { queued, running, succeeded, failed, skipped, total } = run.counts;
  const chips: [string, number, ('success' | 'error' | 'info' | 'default')?][] = [
    ['total', total],
    ['queued', queued],
    ['running', running],
    ['succeeded', succeeded, 'success'],
    ['failed', failed, failed > 0 ? 'error' : 'default'],
    ['skipped', skipped, 'info']
  ];
  return (
    <Stack spacing={1}>
      {total > 0 && (
        <LinearProgress variant="determinate" value={Math.min(100, ((succeeded + failed + skipped) / total) * 100)} />
      )}
      <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
        {chips.map(([key, count, color]) => (
          <Chip key={key} size="small" color={color} label={t(`route.actions.run.count.${key}`, { count })} />
        ))}
      </Stack>
      {run.results.map(result => (
        <Alert
          key={result.hit_id}
          variant="outlined"
          severity={result.state === 'failed' ? 'error' : result.state === 'skipped' ? 'warning' : 'info'}
        >
          <Stack spacing={0.25}>
            <Typography variant="subtitle2">
              {result.hit_id}
              {' · '}
              {t(`route.actions.run.result.${result.state}`)}
            </Typography>
            <Typography variant="caption">{t('route.actions.run.attempts', { count: result.attempts })}</Typography>
            {result.reason && <Typography variant="body2">{result.reason}</Typography>}
            {result.message && <Typography variant="body2">{result.message}</Typography>}
          </Stack>
        </Alert>
      ))}
    </Stack>
  );
};

export default ActionRunHistory;
