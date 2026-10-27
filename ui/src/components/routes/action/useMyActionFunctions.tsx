import { Terminal } from '@mui/icons-material';
import { LinearProgress, Stack } from '@mui/material';
import api from 'api';
import type { HowlerSearchResponse } from 'api/search';
import type { RecievedDataType } from 'components/app/providers/SocketProvider';
import { SocketContext } from 'components/app/providers/SocketProvider';
import useMyApi from 'components/hooks/useMyApi';
import useMyLocalStorage from 'components/hooks/useMyLocalStorage';
import useMySnackbar from 'components/hooks/useMySnackbar';
import type { ActionReport } from 'models/ActionTypes';
import type { Hit } from 'models/entities/generated/Hit';
import type { Operation } from 'models/entities/generated/Operation';
import { useSnackbar, type SnackbarKey } from 'notistack';
import { useCallback, useContext, useEffect, useId, useMemo, useRef, useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { useLocation, useNavigate, useParams } from 'react-router';
import { v4 as uuid } from 'uuid';
import { StorageKey } from 'utils/constants';

type ActionProgressEvent = {
  request_id: string;
  processed: number;
  total: number;
  run_id?: string;
  revision?: number;
  state?: string;
};

const useMyActionFunctions = () => {
  const { t } = useTranslation();
  const { closeSnackbar } = useSnackbar();
  const { showErrorMessage, showSuccessMessage, showInfoMessage } = useMySnackbar();
  const { dispatchApi } = useMyApi();
  const navigate = useNavigate();
  const location = useLocation();
  const params = useParams();
  const { get } = useMyLocalStorage();
  const authSessionKey = get<string>(StorageKey.APP_TOKEN) ?? '';
  const contextKey = JSON.stringify([authSessionKey, location.pathname, params.id ?? null]);
  const { addListener, removeListener } = useContext(SocketContext);
  const listenerKey = `action-progress-${useId()}`;
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<HowlerSearchResponse<Hit>>();
  const [responseQuery, setResponseQuery] = useState('');
  const [progress, setProgress] = useState<[number, number]>([0, 0]);
  const [requestId, setRequestId] = useState<string>();
  const [report, setReport] = useState<ActionReport>();
  const [stateContextKey, setStateContextKey] = useState(contextKey);
  const activeContextRef = useRef(contextKey);
  const requestSeqRef = useRef(0);
  const progressRevisions = useRef(new Map<string, number>());
  const isCurrentContext = stateContextKey === contextKey;
  const currentReport = isCurrentContext ? report : undefined;
  const setLoadingForContext = useCallback<typeof setLoading>(
    value => {
      if (activeContextRef.current !== contextKey) {
        return;
      }
      setStateContextKey(contextKey);
      setLoading(value);
    },
    [contextKey, setLoading]
  );
  const setResponseForContext = useCallback<typeof setResponse>(
    value => {
      if (activeContextRef.current !== contextKey) {
        return;
      }
      setStateContextKey(contextKey);
      setResponse(value);
    },
    [contextKey, setResponse]
  );

  useEffect(() => {
    if (activeContextRef.current === contextKey) {
      return;
    }
    activeContextRef.current = contextKey;
    requestSeqRef.current += 1;
    progressRevisions.current.clear();
    setStateContextKey(contextKey);
    setLoading(false);
    setResponse(undefined);
    setResponseQuery('');
    setRequestId(undefined);
    setReport(undefined);
    setProgress([0, 0]);
  }, [contextKey]);

  const acceptedRunIds = useMemo(
    () =>
      Object.values(currentReport ?? {}).flatMap(entries =>
        (Array.isArray(entries) ? entries : []).flatMap(entry =>
          entry.status === 'queued' && entry.run_id ? [entry.run_id] : []
        )
      ),
    [currentReport]
  );

  const handler = useCallback(
    (data: RecievedDataType<ActionProgressEvent>) => {
      if (activeContextRef.current !== contextKey || data.type !== 'action' || data.request_id !== requestId) {
        return;
      }
      const revisionKey = typeof data.run_id === 'string' ? data.run_id : data.request_id;
      const knownRevision = progressRevisions.current.get(revisionKey) ?? -1;
      if (typeof data.revision === 'number' && data.revision < knownRevision) {
        return;
      }
      setStateContextKey(contextKey);
      if (typeof data.revision === 'number') {
        progressRevisions.current.set(revisionKey, data.revision);
      }
      setProgress([data.processed, data.total]);
      if (data.state === 'completed') {
        setRequestId(undefined);
        setProgress([0, 0]);
      }
    },
    [contextKey, requestId]
  );

  useEffect(() => {
    addListener<ActionProgressEvent>(listenerKey, handler);
    return () => removeListener(listenerKey);
  }, [addListener, handler, listenerKey, removeListener]);

  const onSearch = useCallback(
    async (query: string) => {
      const sequence = requestSeqRef.current;
      if (activeContextRef.current !== contextKey) {
        return;
      }
      const result = await dispatchApi(api.search.hit.post({ query, rows: 3, track_total_hits: true }));
      if (sequence !== requestSeqRef.current || activeContextRef.current !== contextKey) {
        return;
      }
      setStateContextKey(contextKey);
      setResponse(result);
      setResponseQuery(query);
    },
    [contextKey, dispatchApi]
  );

  const saveAction = useCallback(
    async (name: string, query: string, operations: Operation[], triggers: string[]) => {
      if (!query) {
        showErrorMessage(t('route.actions.query.empty'));
        return;
      }
      if (activeContextRef.current !== contextKey) {
        return;
      }
      const sequence = requestSeqRef.current;
      setStateContextKey(contextKey);
      setLoading(true);
      try {
        if (params.id) {
          const result = await dispatchApi(api.action.put(params.id, { name, query, operations }), {
            showError: true,
            throwError: false
          });
          if (sequence !== requestSeqRef.current || activeContextRef.current !== contextKey) {
            return;
          }
          if (result) {
            void navigate(`/action/${params.id}`);
          }
        } else {
          const result = await dispatchApi(api.action.post({ name, query, operations, triggers }), {
            showError: true,
            throwError: false
          });
          if (sequence !== requestSeqRef.current || activeContextRef.current !== contextKey) {
            return;
          }
          if (result) {
            void navigate(`/action/${result.action_id}`);
          }
        }
      } finally {
        if (sequence === requestSeqRef.current && activeContextRef.current === contextKey) {
          setStateContextKey(contextKey);
          setLoading(false);
        }
      }
    },
    [contextKey, dispatchApi, navigate, params.id, showErrorMessage, t]
  );

  const submitAction = useCallback(
    async (query: string, operations: Operation[]): Promise<void> => {
      if (!query) {
        showErrorMessage(t('route.actions.query.empty'));
        return;
      }
      if (activeContextRef.current !== contextKey) {
        return;
      }
      const sequence = requestSeqRef.current;
      setStateContextKey(contextKey);
      setLoading(true);
      const reqId = uuid();
      setRequestId(reqId);
      progressRevisions.current.clear();
      setReport(undefined);
      let acceptedAsyncRun = false;
      try {
        const result = await dispatchApi(api.action.execute.post({ request_id: reqId, query, operations }), {
          throwError: false,
          showError: true
        });
        if (sequence !== requestSeqRef.current || activeContextRef.current !== contextKey) {
          return;
        }
        acceptedAsyncRun = Object.values(result ?? {})
          .flat()
          .some(item => item.status === 'queued' && !!item.run_id);
        setReport(result);
      } finally {
        if (sequence === requestSeqRef.current && activeContextRef.current === contextKey) {
          setStateContextKey(contextKey);
          setLoading(false);
          if (!acceptedAsyncRun) {
            setRequestId(undefined);
            setProgress([0, 0]);
          }
          void onSearch(query);
        }
      }
    },
    [contextKey, dispatchApi, onSearch, showErrorMessage, t]
  );

  const executeAction = useCallback(
    async (actionId: string, query?: string) => {
      if (activeContextRef.current !== contextKey) {
        return;
      }
      const sequence = requestSeqRef.current;
      setStateContextKey(contextKey);
      setLoading(true);
      const reqId = uuid();
      setRequestId(reqId);
      progressRevisions.current.clear();
      setReport(undefined);
      let acceptedAsyncRun = false;
      let snackbarKey: SnackbarKey | null = null;
      try {
        const actionResponse = await api.search.action.post({ query: `action_id:${actionId}`, rows: 1 });
        if (sequence !== requestSeqRef.current || activeContextRef.current !== contextKey) {
          return;
        }
        const actionName = actionResponse?.items[0]?.name ?? t('unknown');
        snackbarKey = showInfoMessage(
          <Stack spacing={1} width="100%" mb={-2} pb={1}>
            <Stack direction="row" spacing={1} px="20px" pt="6px" pb="2px">
              <Terminal fontSize="small" sx={{ mr: 2 }} />
              <span>
                <Trans i18nKey="actions.running" values={{ action: actionName }} />
              </span>
            </Stack>
            <LinearProgress color="inherit" sx={theme => ({ borderRadius: theme.shape.borderRadius })} />
          </Stack>,
          0,
          {
            persist: true,
            hideIconVariant: true,
            style: { padding: 0, display: 'flex', flexDirection: 'column', alignItems: 'stretch' }
          }
        );

        const result = await dispatchApi(api.action.execute.post({ request_id: reqId, query, action_id: actionId }), {
          throwError: false,
          showError: false
        });
        if (sequence !== requestSeqRef.current || activeContextRef.current !== contextKey) {
          return;
        }
        setReport(result);
        if (!result) {
          showErrorMessage(<Trans i18nKey="actions.error" values={{ action: actionName, message: t('unknown') }} />);
          return;
        }

        const results = Object.values(result).flat();
        const queued = results.filter(item => item.status === 'queued' && !!item.run_id);
        acceptedAsyncRun = queued.length > 0;
        for (const [outcome, key, notify] of [
          ['error', 'actions.error', showErrorMessage],
          ['skipped', 'actions.skipped', showInfoMessage]
        ] as const) {
          const messages = results
            .filter(item => item.outcome === outcome)
            .map(item => item.message)
            .join(', ');
          if (messages) {
            notify(<Trans i18nKey={key} values={{ action: actionName, messages }} />);
          }
        }
        if (queued.length) {
          if (snackbarKey) {
            closeSnackbar(snackbarKey);
          }
          snackbarKey = null;
          showInfoMessage(<Trans i18nKey="actions.queued" values={{ action: actionName }} />);
        } else if (results.some(item => item.outcome === 'success' && item.status !== 'queued')) {
          showSuccessMessage(<Trans i18nKey="actions.succeeded" values={{ action: actionName }} />);
        }
      } finally {
        if (snackbarKey) {
          closeSnackbar(snackbarKey);
        }
        if (sequence === requestSeqRef.current && activeContextRef.current === contextKey) {
          setStateContextKey(contextKey);
          setLoading(false);
          if (!acceptedAsyncRun) {
            setRequestId(undefined);
            setProgress([0, 0]);
          }
        }
      }
    },
    [closeSnackbar, contextKey, dispatchApi, showErrorMessage, showInfoMessage, showSuccessMessage, t]
  );

  const deleteAction = useCallback(
    async (actionId: string) => {
      if (activeContextRef.current !== contextKey) {
        return;
      }
      const sequence = requestSeqRef.current;
      setStateContextKey(contextKey);
      setLoading(true);
      try {
        const detailedActionView = location.pathname.endsWith(actionId);
        await dispatchApi(api.action.del(actionId, detailedActionView ? 'wait_for' : undefined), { throwError: true });
        if (sequence !== requestSeqRef.current || activeContextRef.current !== contextKey) {
          return;
        }
        if (detailedActionView) {
          void navigate('/action');
        }
      } finally {
        if (sequence === requestSeqRef.current && activeContextRef.current === contextKey) {
          setStateContextKey(contextKey);
          setLoading(false);
        }
      }
    },
    [contextKey, dispatchApi, location.pathname, navigate]
  );

  return {
    loading: isCurrentContext ? loading : false,
    setLoading: setLoadingForContext,
    response: isCurrentContext ? response : undefined,
    setResponse: setResponseForContext,
    responseQuery: isCurrentContext ? responseQuery : '',
    report: currentReport,
    requestId: isCurrentContext ? requestId : undefined,
    progress: isCurrentContext ? progress : [0, 0],
    acceptedRunIds,
    onSearch,
    saveAction,
    submitAction,
    executeAction,
    deleteAction
  };
};

export default useMyActionFunctions;
