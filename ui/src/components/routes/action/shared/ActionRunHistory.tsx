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

type ActionRunEvent = {
  operation_id: string;
  run_id: string;
  request_id: string;
  revision: number;
  state: ActionRunState;
  processed: number;
  total: number;
};

const ACTIVE_STATES: ActionRunState[] = ['queued', 'running'];
const EMPTY_ACCEPTED_RUN_IDS: string[] = [];

type ActionRunHistoryProps = {
  actionId?: string;
  requestId?: string;
  contextId?: string;
  acceptedRunIds?: string[];
};

const ActionRunHistory: FC<ActionRunHistoryProps> = props => {
  const { get } = useMyLocalStorage();
  const authSessionKey = get<string>(StorageKey.APP_TOKEN) ?? '';
  const acceptedRunIds = props.acceptedRunIds ?? EMPTY_ACCEPTED_RUN_IDS;
  const acceptedRunKey = [...acceptedRunIds].sort().join(',');
  const sessionKey = JSON.stringify([
    authSessionKey,
    props.actionId ?? null,
    props.requestId ?? null,
    props.contextId ?? null,
    acceptedRunKey
  ]);

  return <ActionRunHistorySession key={sessionKey} {...props} acceptedRunIds={acceptedRunIds} />;
};

const getApiStatusCode = (error: unknown): number | undefined => {
  if (!(error instanceof Error)) {
    return undefined;
  }

  return (error.cause as HowlerResponse<unknown> | undefined)?.api_status_code;
};

const isUnavailableStatus = (statusCode?: number) => statusCode === 401 || statusCode === 403 || statusCode === 404;

const ActionRunHistorySession: FC<ActionRunHistoryProps & { acceptedRunIds: string[] }> = ({
  actionId,
  requestId,
  contextId,
  acceptedRunIds
}) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const { addListener, removeListener } = useContext(SocketContext);
  const listenerId = useId();
  const listenerKey = `ai-triage-runs-${listenerId}`;
  const [items, setItems] = useState<ActionRunSummary[]>([]);
  const [selection, setSelection] = useState<{ queryKey: string; runId: string }>();
  const [selectedRun, setSelectedRun] = useState<ActionRun>();
  const [loadedKey, setLoadedKey] = useState<string>();
  const [detailLoading, setDetailLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [nextOffset, setNextOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [pendingAcceptedIds, setPendingAcceptedIds] = useState(() => new Set(acceptedRunIds));
  const [activeCachedRunIds, setActiveCachedRunIds] = useState(() => new Set<string>());
  const [listRetryPending, setListRetryPending] = useState(false);
  const [retryingRunIds, setRetryingRunIds] = useState(() => new Set<string>());
  const listSequence = useRef(0);
  const detailSequence = useRef(0);
  const selectedRunIdRef = useRef<string | undefined>(undefined);
  const selectedQueryKeyRef = useRef<string | undefined>(undefined);
  const revisionCache = useRef(new Map<string, number>());
  const summaryCache = useRef(new Map<string, ActionRunSummary>());
  const unavailableRuns = useRef(new Set<string>());
  const trackedRunSequence = useRef(new Map<string, number>());
  const queryKey = JSON.stringify([actionId, requestId, contextId]);
  const selectedRunId = selection?.queryKey === queryKey ? selection.runId : undefined;
  const visibleItems = loadedKey === queryKey ? items : [];
  const isLoading = loadedKey !== queryKey;

  const clearPrivateData = useCallback(() => {
    listSequence.current += 1;
    detailSequence.current += 1;
    trackedRunSequence.current.forEach((sequence, runId) => trackedRunSequence.current.set(runId, sequence + 1));
    setItems([]);
    setLoadedKey(queryKey);
    setNextOffset(0);
    setHasMore(false);
    setPendingAcceptedIds(new Set());
    setActiveCachedRunIds(new Set());
    setListRetryPending(false);
    setRetryingRunIds(new Set());
    setRefreshing(false);
    setLoadingMore(false);
    setDetailLoading(false);
    setSelectedRun(undefined);
    setSelection(undefined);
    selectedRunIdRef.current = undefined;
    selectedQueryKeyRef.current = undefined;
    revisionCache.current.clear();
    summaryCache.current.clear();
    unavailableRuns.current.clear();
  }, [queryKey]);

  const clearUnavailableRun = useCallback((runId: string) => {
    const wasSelected = selectedRunIdRef.current === runId;
    listSequence.current += 1;
    unavailableRuns.current.add(runId);
    trackedRunSequence.current.set(runId, (trackedRunSequence.current.get(runId) ?? 0) + 1);
    revisionCache.current.delete(runId);
    summaryCache.current.delete(runId);
    setActiveCachedRunIds(current => {
      const next = new Set(current);
      next.delete(runId);
      return next;
    });
    setPendingAcceptedIds(current => {
      const next = new Set(current);
      next.delete(runId);
      return next;
    });
    setRetryingRunIds(current => {
      const next = new Set(current);
      next.delete(runId);
      return next;
    });
    setRefreshing(false);
    setLoadingMore(false);
    setSelectedRun(current => (current?.run_id === runId ? undefined : current));
    setItems(current => current.filter(item => item.run_id !== runId));
    setSelection(current => (current?.runId === runId ? undefined : current));
    if (wasSelected) {
      selectedRunIdRef.current = undefined;
      selectedQueryKeyRef.current = undefined;
      detailSequence.current += 1;
      setDetailLoading(false);
    }
  }, []);

  const rememberSummary = useCallback((summary: ActionRunSummary) => {
    setActiveCachedRunIds(current => {
      const shouldBeActive = ACTIVE_STATES.includes(summary.state);
      if (current.has(summary.run_id) === shouldBeActive) {
        return current;
      }

      const next = new Set(current);
      if (shouldBeActive) {
        next.add(summary.run_id);
      } else {
        next.delete(summary.run_id);
      }
      return next;
    });
  }, []);

  const getLatestSummary = useCallback(
    (summary: ActionRunSummary) => {
      const cachedRevision = revisionCache.current.get(summary.run_id) ?? -1;
      const cachedSummary = summaryCache.current.get(summary.run_id);
      const latest = cachedSummary && cachedRevision > summary.revision ? cachedSummary : summary;
      if (latest === summary) {
        revisionCache.current.set(summary.run_id, summary.revision);
        summaryCache.current.set(summary.run_id, summary);
      }
      rememberSummary(latest);
      return latest;
    },
    [rememberSummary]
  );

  const refreshList = useCallback(
    async (quiet = false) => {
      const sequence = ++listSequence.current;
      if (quiet) {
        setRefreshing(true);
      }

      try {
        const response = await dispatchApi(
          api.action.runs.list({
            operation_id: 'ai_triage',
            action_id: actionId,
            request_id: requestId,
            offset: 0,
            rows: 20
          }),
          { throwError: true, showError: false }
        );

        if (sequence !== listSequence.current) {
          return;
        }

        if (!response) {
          clearPrivateData();
          return;
        }

        const nextItems = response.items
          .filter(summary => !unavailableRuns.current.has(summary.run_id))
          .map(getLatestSummary);

        setItems(current => {
          const mergedItems = [...nextItems];
          const includedIds = new Set(mergedItems.map(item => item.run_id));
          current.forEach(item => {
            const latest = summaryCache.current.get(item.run_id) ?? item;
            const tracked = quiet || acceptedRunIds.includes(item.run_id);
            if (tracked && !includedIds.has(item.run_id) && !unavailableRuns.current.has(item.run_id)) {
              mergedItems.push(latest);
              includedIds.add(item.run_id);
            }
          });
          return mergedItems;
        });
        setLoadedKey(queryKey);
        setNextOffset(current =>
          quiet ? Math.max(current, response.offset + response.rows) : response.offset + response.rows
        );
        setHasMore(response.has_more);
        setPendingAcceptedIds(current => {
          const remaining = new Set(current);
          response.items.forEach(summary => remaining.delete(summary.run_id));
          return remaining.size === current.size ? current : remaining;
        });
        setListRetryPending(false);
      } catch (error) {
        if (sequence === listSequence.current) {
          if (isUnavailableStatus(getApiStatusCode(error))) {
            clearPrivateData();
          } else {
            setListRetryPending(true);
          }
        }
      } finally {
        if (sequence === listSequence.current) {
          setLoadingMore(false);
          if (quiet) {
            setRefreshing(false);
          }
        }
      }
    },
    [acceptedRunIds, actionId, clearPrivateData, dispatchApi, getLatestSummary, queryKey, requestId]
  );

  const loadMore = useCallback(async () => {
    if (loadedKey !== queryKey || !hasMore) {
      return;
    }

    const sequence = ++listSequence.current;
    setLoadingMore(true);
    try {
      const response = await dispatchApi(
        api.action.runs.list({
          operation_id: 'ai_triage',
          action_id: actionId,
          request_id: requestId,
          offset: nextOffset,
          rows: 20
        }),
        { throwError: true, showError: false }
      );

      if (sequence !== listSequence.current) {
        return;
      }

      if (!response) {
        clearPrivateData();
        return;
      }

      const pageItems = response.items
        .filter(summary => !unavailableRuns.current.has(summary.run_id))
        .map(getLatestSummary);

      setItems(current => {
        const mergedItems = [...current];
        pageItems.forEach(summary => {
          const existingIndex = mergedItems.findIndex(item => item.run_id === summary.run_id);
          if (existingIndex < 0) {
            mergedItems.push(summary);
          } else if (mergedItems[existingIndex]!.revision < summary.revision) {
            mergedItems[existingIndex] = summary;
          }
        });
        return mergedItems;
      });
      setNextOffset(response.offset + response.rows);
      setHasMore(response.has_more);
      setPendingAcceptedIds(current => {
        const remaining = new Set(current);
        response.items.forEach(summary => remaining.delete(summary.run_id));
        return remaining.size === current.size ? current : remaining;
      });
      setListRetryPending(false);
    } catch (error) {
      if (sequence === listSequence.current) {
        if (isUnavailableStatus(getApiStatusCode(error))) {
          clearPrivateData();
        } else {
          setListRetryPending(true);
        }
      }
    } finally {
      if (sequence === listSequence.current) {
        setLoadingMore(false);
      }
    }
  }, [actionId, clearPrivateData, dispatchApi, getLatestSummary, hasMore, loadedKey, nextOffset, queryKey, requestId]);

  const fetchRun = useCallback(
    async (runId: string) => {
      const sequence = ++detailSequence.current;
      setDetailLoading(true);

      try {
        const result = await dispatchApi(api.action.runs.get(runId), { throwError: true, showError: false });
        if (
          sequence !== detailSequence.current ||
          selectedRunIdRef.current !== runId ||
          selectedQueryKeyRef.current !== queryKey
        ) {
          return;
        }

        if (!result) {
          clearPrivateData();
          return;
        }

        unavailableRuns.current.delete(runId);
        setPendingAcceptedIds(current => {
          const next = new Set(current);
          next.delete(runId);
          return next;
        });
        setRetryingRunIds(current => {
          const next = new Set(current);
          next.delete(runId);
          return next;
        });
        const cachedRevision = revisionCache.current.get(runId) ?? -1;
        if (result.revision < cachedRevision) {
          setSelectedRun(current =>
            current?.run_id === runId && current.revision < cachedRevision ? undefined : current
          );
          setRetryingRunIds(current => new Set(current).add(runId));
          return;
        }

        revisionCache.current.set(runId, result.revision);
        summaryCache.current.set(runId, result);
        rememberSummary(result);
        setSelectedRun(result);
        setItems(current =>
          current.map(item => (item.run_id === runId && item.revision < result.revision ? result : item))
        );
      } catch (error) {
        if (sequence !== detailSequence.current || selectedRunIdRef.current !== runId) {
          return;
        }

        const statusCode = getApiStatusCode(error);
        if (statusCode === 401) {
          clearPrivateData();
        } else if (statusCode === 403 || statusCode === 404) {
          clearUnavailableRun(runId);
        } else {
          setRetryingRunIds(current => new Set(current).add(runId));
        }
      } finally {
        if (sequence === detailSequence.current) {
          setDetailLoading(false);
        }
      }
    },
    [clearPrivateData, clearUnavailableRun, dispatchApi, queryKey, rememberSummary]
  );

  const fetchTrackedRun = useCallback(
    async (runId: string) => {
      const sequence = (trackedRunSequence.current.get(runId) ?? 0) + 1;
      trackedRunSequence.current.set(runId, sequence);

      try {
        const result = await dispatchApi(api.action.runs.get(runId), { throwError: true, showError: false });
        if (trackedRunSequence.current.get(runId) !== sequence) {
          return;
        }

        if (!result) {
          clearPrivateData();
          return;
        }

        if ((actionId && result.action_id !== actionId) || (requestId && result.request_id !== requestId)) {
          clearUnavailableRun(runId);
          return;
        }

        const knownRevision = revisionCache.current.get(runId) ?? -1;
        if (result.revision < knownRevision) {
          setRetryingRunIds(current => new Set(current).add(runId));
          return;
        }

        unavailableRuns.current.delete(runId);
        const latest = getLatestSummary(result);
        setPendingAcceptedIds(current => {
          if (!current.has(runId)) {
            return current;
          }
          const next = new Set(current);
          next.delete(runId);
          return next;
        });
        setRetryingRunIds(current => {
          if (!current.has(runId)) {
            return current;
          }
          const next = new Set(current);
          next.delete(runId);
          return next;
        });
        setItems(current => {
          const index = current.findIndex(item => item.run_id === runId);
          if (index < 0) {
            return [latest, ...current];
          }
          if (current[index]!.revision >= latest.revision) {
            return current;
          }
          return current.map(item => (item.run_id === runId ? latest : item));
        });
      } catch (error) {
        if (trackedRunSequence.current.get(runId) !== sequence) {
          return;
        }

        const statusCode = getApiStatusCode(error);
        if (statusCode === 401) {
          clearPrivateData();
        } else if (statusCode === 403 || statusCode === 404) {
          clearUnavailableRun(runId);
        } else {
          setRetryingRunIds(current => new Set(current).add(runId));
        }
      }
    },
    [actionId, clearPrivateData, clearUnavailableRun, dispatchApi, getLatestSummary, requestId]
  );

  useEffect(() => {
    pendingAcceptedIds.forEach(runId => void fetchTrackedRun(runId));
  }, [fetchTrackedRun, pendingAcceptedIds]);

  const refreshSelectedRun = useCallback(() => {
    const runId = selectedRunIdRef.current;
    if (runId && selectedQueryKeyRef.current === queryKey) {
      void fetchRun(runId);
    }
  }, [fetchRun, queryKey]);

  const refreshTrackedRuns = useCallback(() => {
    new Set([...activeCachedRunIds, ...pendingAcceptedIds]).forEach(runId => void fetchTrackedRun(runId));
  }, [activeCachedRunIds, fetchTrackedRun, pendingAcceptedIds]);

  const handleActionEvent = useCallback(
    (data: RecievedDataType<ActionRunEvent>) => {
      if (data.type !== 'action' || data.operation_id !== 'ai_triage' || !data.run_id) {
        return;
      }

      if (requestId && data.request_id !== requestId) {
        return;
      }

      const cachedRevision = revisionCache.current.get(data.run_id) ?? -1;
      if (data.revision < cachedRevision) {
        return;
      }

      revisionCache.current.set(data.run_id, data.revision);
      void refreshList(true);
      // This callback runs on socket events, outside render; the refs track the current selection.
      // oxlint-disable-next-line react/refs
      if (selectedRunIdRef.current === data.run_id && selectedQueryKeyRef.current === queryKey) {
        void fetchRun(data.run_id);
      }
    },
    [fetchRun, queryKey, refreshList, requestId]
  );

  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect
    void refreshList();
    return () => {
      listSequence.current += 1;
      detailSequence.current += 1;
    };
  }, [refreshList]);

  useEffect(() => {
    addListener<ActionRunEvent>(listenerKey, handleActionEvent);
    return () => removeListener(listenerKey);
  }, [addListener, handleActionEvent, listenerKey, removeListener]);

  const hasActiveRuns =
    visibleItems.some(item => ACTIVE_STATES.includes(item.state)) ||
    (selectedRun ? ACTIVE_STATES.includes(selectedRun.state) : false) ||
    activeCachedRunIds.size > 0 ||
    pendingAcceptedIds.size > 0 ||
    listRetryPending ||
    retryingRunIds.size > 0 ||
    (selectedRunId !== undefined && (detailLoading || retryingRunIds.has(selectedRunId)));

  useEffect(() => {
    if (!hasActiveRuns) {
      return;
    }

    const interval = window.setInterval(() => {
      void refreshList(true);
      refreshSelectedRun();
      refreshTrackedRuns();
    }, 3000);

    return () => window.clearInterval(interval);
  }, [hasActiveRuns, refreshList, refreshSelectedRun, refreshTrackedRuns]);

  const selectRun = (runId: string) => {
    if (selectedRunIdRef.current === runId && selectedQueryKeyRef.current === queryKey) {
      selectedRunIdRef.current = undefined;
      selectedQueryKeyRef.current = undefined;
      setSelection(undefined);
      setSelectedRun(undefined);
      detailSequence.current += 1;
      return;
    }

    selectedRunIdRef.current = runId;
    selectedQueryKeyRef.current = queryKey;
    setSelection({ queryKey, runId });
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
      {pendingAcceptedIds.size > 0 && (
        <Alert severity="info" variant="outlined">
          <Stack spacing={0.5}>
            <Typography>{t('route.actions.run.accepted.pending')}</Typography>
            {[...pendingAcceptedIds].map(runId => (
              <Typography key={runId} variant="caption">
                {t('route.actions.run.id', { runId })}
              </Typography>
            ))}
          </Stack>
        </Alert>
      )}
      {isLoading && visibleItems.length === 0 && <LinearProgress />}
      {!isLoading && visibleItems.length === 0 && (
        <Typography color="text.secondary">{t('route.actions.run.empty')}</Typography>
      )}
      {visibleItems.map(run => (
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
      {loadedKey === queryKey && hasMore && (
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

  return (
    <Stack spacing={1}>
      {total > 0 && (
        <LinearProgress variant="determinate" value={Math.min(100, ((succeeded + failed + skipped) / total) * 100)} />
      )}
      <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
        <Chip size="small" label={t('route.actions.run.count.total', { count: total })} />
        <Chip size="small" label={t('route.actions.run.count.queued', { count: queued })} />
        <Chip size="small" label={t('route.actions.run.count.running', { count: running })} />
        <Chip size="small" color="success" label={t('route.actions.run.count.succeeded', { count: succeeded })} />
        <Chip
          size="small"
          color={failed > 0 ? 'error' : 'default'}
          label={t('route.actions.run.count.failed', { count: failed })}
        />
        <Chip size="small" color="info" label={t('route.actions.run.count.skipped', { count: skipped })} />
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
