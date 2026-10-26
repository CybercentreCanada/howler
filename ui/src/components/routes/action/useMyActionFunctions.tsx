import { Terminal } from '@mui/icons-material';
import { LinearProgress, Stack } from '@mui/material';
import api from 'api';
import type { HowlerSearchResponse } from 'api/search';
import type { RecievedDataType } from 'components/app/providers/SocketProvider';
import { SocketContext } from 'components/app/providers/SocketProvider';
import useMyApi from 'components/hooks/useMyApi';
import useMySnackbar from 'components/hooks/useMySnackbar';
import type { ActionReport } from 'models/ActionTypes';
import type { Hit } from 'models/entities/generated/Hit';
import type { Operation } from 'models/entities/generated/Operation';
import { useSnackbar, type SnackbarKey } from 'notistack';
import { useCallback, useContext, useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { useLocation, useNavigate, useParams } from 'react-router';
import useMyLocalStorage from 'components/hooks/useMyLocalStorage';
import { StorageKey } from 'utils/constants';
import { v4 as uuid } from 'uuid';

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
  const [contextVersion, setContextVersion] = useState(() => ({ key: contextKey, version: 0 }));
  const executionContext = JSON.stringify([
    contextKey,
    contextVersion.key === contextKey ? contextVersion.version : contextVersion.version + 1
  ]);
  const { addListener, removeListener } = useContext(SocketContext);
  const listenerId = useId();
  const listenerKey = `action-progress-${listenerId}`;

  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<HowlerSearchResponse<Hit>>();
  const [responseQuery, setResponseQuery] = useState('');
  const [progress, setProgress] = useState<[number, number]>([0, 0]);
  const [requestId, setRequestId] = useState<string>();
  const [report, setReport] = useState<ActionReport>();
  const executionContextRef = useRef(executionContext);
  const progressRevisions = useRef(new Map<string, number>());

  useLayoutEffect(() => {
    if (contextVersion.key !== contextKey) {
      const nextContextVersion = { key: contextKey, version: contextVersion.version + 1 };
      // oxlint-disable-next-line react/set-state-in-effect
      setContextVersion(nextContextVersion);
      executionContextRef.current = JSON.stringify([contextKey, nextContextVersion.version]);
      progressRevisions.current.clear();
      setLoading(false);
      setResponse(undefined);
      setResponseQuery('');
      setRequestId(undefined);
      setReport(undefined);
      setProgress([0, 0]);
    }
  }, [contextKey, contextVersion]);

  type ActionProgressEvent = {
    request_id: string;
    processed: number;
    total: number;
    run_id?: string;
    revision?: number;
    state?: string;
  };

  const handler = useCallback(
    (data: RecievedDataType<ActionProgressEvent>) => {
      if (executionContextRef.current !== executionContext || data.type !== 'action' || data.request_id !== requestId) {
        return;
      }

      const revision = typeof data.revision === 'number' ? data.revision : undefined;
      const revisionKey = typeof data.run_id === 'string' ? data.run_id : data.request_id;
      const knownRevision = progressRevisions.current.get(revisionKey) ?? -1;
      if (revision !== undefined && revision < knownRevision) {
        return;
      }

      if (revision !== undefined) {
        progressRevisions.current.set(revisionKey, revision);
      }

      setProgress([data.processed, data.total]);
      if ('state' in data && data.state === 'completed') {
        setRequestId(undefined);
        setProgress([0, 0]);
      }
    },
    [executionContext, requestId]
  );

  const onSearch = useCallback(
    async (query: string) => {
      const _response = await dispatchApi(
        api.search.hit.post({
          query,
          rows: 3,
          track_total_hits: true
        })
      );

      if (executionContextRef.current !== executionContext) {
        return;
      }

      setResponse(_response);
      setResponseQuery(query);
    },
    [dispatchApi, executionContext]
  );

  useEffect(() => {
    addListener<ActionProgressEvent>(listenerKey, handler);

    return () => removeListener(listenerKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [handler, listenerKey]);

  return {
    loading: executionContextRef.current === executionContext ? loading : false,
    setLoading,
    response: executionContextRef.current === executionContext ? response : undefined,
    setResponse,
    responseQuery: executionContextRef.current === executionContext ? responseQuery : '',
    report: executionContextRef.current === executionContext ? report : undefined,
    requestId: executionContextRef.current === executionContext ? requestId : undefined,
    progress: executionContextRef.current === executionContext ? progress : [0, 0],
    onSearch,
    saveAction: useCallback(
      async (name: string, query: string, operations: Operation[], triggers: string[]) => {
        try {
          if (!query) {
            showErrorMessage(t('route.actions.query.empty'));
            return;
          }

          if (params.id) {
            setLoading(true);
            const result = await dispatchApi(
              api.action.put(params.id, {
                name,
                query,
                operations
              }),
              { showError: true, throwError: false }
            );

            if (result) {
              void navigate(`/action/${params.id}`);
            }
          } else {
            setLoading(true);
            const newAction = await dispatchApi(
              api.action.post({
                name,
                query,
                operations,
                triggers
              }),
              { showError: true, throwError: false }
            );

            if (newAction) {
              void navigate(`/action/${newAction.action_id}`);
            }
          }
        } finally {
          setLoading(false);
        }
      },
      [dispatchApi, navigate, params.id, showErrorMessage, t]
    ),
    submitAction: useCallback(
      async (query: string, operations: Operation[]): Promise<void> => {
        if (executionContextRef.current !== executionContext) {
          return;
        }

        if (!query) {
          showErrorMessage(t('route.actions.query.empty'));
          return;
        }

        setLoading(true);
        const reqId = uuid();
        const requestContext = executionContext;
        setRequestId(reqId);
        progressRevisions.current.clear();
        setReport(undefined);
        let acceptedAsyncRun = false;

        try {
          const result = await dispatchApi(
            api.action.execute.post({
              request_id: reqId,
              query,
              operations
            }),
            { throwError: false, showError: true }
          );
          if (executionContextRef.current !== requestContext) {
            return;
          }

          acceptedAsyncRun = Object.values(result ?? {})
            .flat()
            .some(item => item.status === 'queued' && !!item.run_id);
          setReport(result);
        } finally {
          if (executionContextRef.current === requestContext) {
            setLoading(false);
            if (!acceptedAsyncRun) {
              setRequestId(undefined);
              setProgress([0, 0]);
            }
            void onSearch(query);
          }
        }
      },
      [dispatchApi, executionContext, onSearch, showErrorMessage, t]
    ),
    executeAction: useCallback(
      async (actionId: string, query?: string) => {
        if (executionContextRef.current !== executionContext) {
          return;
        }

        setLoading(true);
        const reqId = uuid();
        const requestContext = executionContext;
        setRequestId(reqId);
        progressRevisions.current.clear();
        setReport(undefined);
        let acceptedAsyncRun = false;

        let key: SnackbarKey | null = null;
        try {
          const actionResponse = await api.search.action.post({ query: `action_id:${actionId}`, rows: 1 });
          if (executionContextRef.current !== requestContext) {
            return;
          }
          const actionName = actionResponse?.items[0]?.name ?? t('unknown');

          key = showInfoMessage(
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

          const result = await dispatchApi(
            api.action.execute.post({
              request_id: reqId,
              query,
              action_id: actionId
            }),
            { throwError: false, showError: false }
          );

          if (executionContextRef.current !== requestContext) {
            return;
          }

          setReport(result);

          if (!result) {
            showErrorMessage(<Trans i18nKey="actions.error" values={{ action: actionName, message: t('unknown') }} />);
            return;
          }

          const allItems = Object.values(result).flat();
          const queued = allItems.filter(item => item.status === 'queued' && !!item.run_id);
          acceptedAsyncRun = queued.length > 0;
          const errors = allItems.filter(item => item.outcome === 'error');
          const skipped = allItems.filter(item => item.outcome === 'skipped');
          const succeeded = allItems.filter(item => item.outcome === 'success' && item.status !== 'queued');

          if (errors.length > 0) {
            showErrorMessage(
              <Trans
                i18nKey="actions.error"
                values={{ action: actionName, messages: errors.map(error => error.message).join(', ') }}
              />
            );
          }

          if (skipped.length > 0) {
            showInfoMessage(
              <Trans
                i18nKey="actions.skipped"
                values={{
                  action: actionName,
                  messages: skipped.map(skippedAction => skippedAction.message).join(', ')
                }}
              />
            );
          }

          if (queued.length > 0) {
            if (key) {
              closeSnackbar(key);
              key = null;
            }
            showInfoMessage(<Trans i18nKey="actions.queued" values={{ action: actionName }} />);
          } else if (succeeded.length > 0) {
            showSuccessMessage(<Trans i18nKey="actions.succeeded" values={{ action: actionName }} />);
          }
        } finally {
          if (key) {
            closeSnackbar(key);
          }
          if (executionContextRef.current === requestContext) {
            setLoading(false);
          }
          if (executionContextRef.current === requestContext && !acceptedAsyncRun) {
            setRequestId(undefined);
            setProgress([0, 0]);
          }
        }
      },
      [closeSnackbar, dispatchApi, executionContext, showInfoMessage, showSuccessMessage, showErrorMessage, t]
    ),
    deleteAction: useCallback(
      async (actionId: string) => {
        setLoading(true);

        try {
          const detailedActionView = location.pathname.endsWith(actionId);

          await dispatchApi(api.action.del(actionId, detailedActionView ? 'wait_for' : undefined), {
            throwError: true
          });

          if (detailedActionView) {
            void navigate('/action');
          }
        } finally {
          setLoading(false);
        }
      },
      [dispatchApi, location.pathname, navigate]
    )
  };
};

export default useMyActionFunctions;
