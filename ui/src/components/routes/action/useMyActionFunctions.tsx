import { Terminal } from '@mui/icons-material';
import { LinearProgress, Stack } from '@mui/material';
import api from 'api';
import type { HowlerSearchResponse } from 'api/search';
import useMyApi from 'components/hooks/useMyApi';
import useMyLocalStorage from 'components/hooks/useMyLocalStorage';
import useMySnackbar from 'components/hooks/useMySnackbar';
import type { ActionReport } from 'models/ActionTypes';
import type { Hit } from 'models/entities/generated/Hit';
import type { Operation } from 'models/entities/generated/Operation';
import { useSnackbar, type SnackbarKey } from 'notistack';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { useLocation, useNavigate, useParams } from 'react-router';
import { v4 as uuid } from 'uuid';
import { StorageKey } from 'utils/constants';

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

  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<HowlerSearchResponse<Hit>>();
  const [responseQuery, setResponseQuery] = useState('');
  const [report, setReport] = useState<ActionReport>();
  const [stateContextKey, setStateContextKey] = useState(contextKey);
  const [stateContextGeneration, setStateContextGeneration] = useState(0);
  const activeContextRef = useRef({ contextKey, generation: 0 });
  const mountedRef = useRef(true);
  const contextGeneration = stateContextGeneration;
  const isCurrentVisit = useCallback(
    (generation: number) =>
      mountedRef.current &&
      activeContextRef.current.contextKey === contextKey &&
      activeContextRef.current.generation === generation,
    [contextKey]
  );
  const markCurrentVisit = useCallback(
    (generation: number) => {
      if (!isCurrentVisit(generation)) {
        return false;
      }
      setStateContextKey(contextKey);
      setStateContextGeneration(generation);
      return true;
    },
    [contextKey, isCurrentVisit]
  );
  const isCurrentContext = stateContextKey === contextKey;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (activeContextRef.current.contextKey === contextKey) {
      return;
    }

    const generation = activeContextRef.current.generation + 1;
    activeContextRef.current = { contextKey, generation };
    setStateContextKey(contextKey);
    setStateContextGeneration(generation);
    setLoading(false);
    setResponse(undefined);
    setResponseQuery('');
    setReport(undefined);
  }, [contextKey]);

  const setLoadingForContext = useCallback(
    (value: boolean) => {
      if (!markCurrentVisit(contextGeneration)) {
        return;
      }
      setLoading(value);
    },
    [contextGeneration, markCurrentVisit]
  );

  const setResponseForContext = useCallback(
    (value: HowlerSearchResponse<Hit> | undefined) => {
      if (!markCurrentVisit(contextGeneration)) {
        return;
      }
      setResponse(value);
    },
    [contextGeneration, markCurrentVisit]
  );

  const onSearch = useCallback(
    async (query: string) => {
      const result = await dispatchApi(
        api.search.hit.post({
          query,
          rows: 3,
          track_total_hits: true
        })
      );

      if (!markCurrentVisit(contextGeneration)) {
        return;
      }

      setResponse(result);
      setResponseQuery(query);
    },
    [contextGeneration, dispatchApi, markCurrentVisit]
  );

  return {
    contextReady: isCurrentContext,
    loading: isCurrentContext ? loading : false,
    setLoading: setLoadingForContext,
    response: isCurrentContext ? response : undefined,
    setResponse: setResponseForContext,
    responseQuery: isCurrentContext ? responseQuery : '',
    report: isCurrentContext ? report : undefined,
    onSearch,
    saveAction: useCallback(
      async (name: string, query: string, operations: Operation[], triggers: string[]) => {
        try {
          if (!isCurrentVisit(contextGeneration)) {
            return;
          }
          if (!query) {
            showErrorMessage(t('route.actions.query.empty'));
            return;
          }

          if (params.id) {
            setLoadingForContext(true);
            const result = await dispatchApi(
              api.action.put(params.id, {
                name,
                query,
                operations
              }),
              { showError: true, throwError: false }
            );

            if (!isCurrentVisit(contextGeneration)) {
              return;
            }
            if (result) {
              void navigate(`/action/${params.id}`);
            }
          } else {
            setLoadingForContext(true);
            const newAction = await dispatchApi(
              api.action.post({
                name,
                query,
                operations,
                triggers
              }),
              { showError: true, throwError: false }
            );

            if (!isCurrentVisit(contextGeneration)) {
              return;
            }
            if (newAction) {
              void navigate(`/action/${newAction.action_id}`);
            }
          }
        } finally {
          setLoadingForContext(false);
        }
      },
      [contextGeneration, dispatchApi, isCurrentVisit, navigate, params.id, setLoadingForContext, showErrorMessage, t]
    ),
    submitAction: useCallback(
      async (query: string, operations: Operation[]): Promise<void> => {
        if (!isCurrentVisit(contextGeneration)) {
          return;
        }
        if (!query) {
          showErrorMessage(t('route.actions.query.empty'));
          return;
        }

        setLoadingForContext(true);
        setReport(undefined);

        try {
          const result = await dispatchApi(
            api.action.execute.post({
              request_id: uuid(),
              query,
              operations
            }),
            { throwError: false, showError: true }
          );
          if (markCurrentVisit(contextGeneration)) {
            setReport(result);
          }
        } finally {
          if (isCurrentVisit(contextGeneration)) {
            setLoadingForContext(false);
            void onSearch(query);
          }
        }
      },
      [
        contextGeneration,
        dispatchApi,
        isCurrentVisit,
        markCurrentVisit,
        onSearch,
        setLoadingForContext,
        showErrorMessage,
        t
      ]
    ),
    executeAction: useCallback(
      async (actionId: string, query?: string) => {
        if (!isCurrentVisit(contextGeneration)) {
          return;
        }
        setLoadingForContext(true);
        setReport(undefined);

        let key: SnackbarKey | null = null;
        try {
          const actionResponse = await api.search.action.post({ query: `action_id:${actionId}`, rows: 1 });
          if (!isCurrentVisit(contextGeneration)) {
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
              request_id: uuid(),
              query,
              action_id: actionId
            }),
            { throwError: false, showError: false }
          );

          if (!isCurrentVisit(contextGeneration)) {
            return;
          }

          if (markCurrentVisit(contextGeneration)) {
            setReport(result);
          }

          if (!result) {
            showErrorMessage(<Trans i18nKey="actions.error" values={{ action: actionName, message: t('unknown') }} />);
            return;
          }

          const allItems = Object.values(result).flat();
          const errors = allItems.filter(item => item.outcome === 'error');
          const skipped = allItems.filter(item => item.outcome === 'skipped');
          const succeeded = allItems.filter(item => item.outcome === 'success');

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

          if (succeeded.length > 0) {
            showSuccessMessage(<Trans i18nKey="actions.succeeded" values={{ action: actionName }} />);
          }
        } finally {
          if (key) {
            closeSnackbar(key);
          }
          setLoadingForContext(false);
        }
      },
      [
        closeSnackbar,
        contextGeneration,
        dispatchApi,
        isCurrentVisit,
        markCurrentVisit,
        setLoadingForContext,
        showInfoMessage,
        showSuccessMessage,
        showErrorMessage,
        t
      ]
    ),
    deleteAction: useCallback(
      async (actionId: string) => {
        if (!isCurrentVisit(contextGeneration)) {
          return;
        }
        setLoadingForContext(true);

        try {
          const detailedActionView = location.pathname.endsWith(actionId);

          await dispatchApi(api.action.del(actionId, detailedActionView ? 'wait_for' : undefined), {
            throwError: true
          });

          if (isCurrentVisit(contextGeneration) && detailedActionView) {
            void navigate('/action');
          }
        } finally {
          setLoadingForContext(false);
        }
      },
      [contextGeneration, dispatchApi, isCurrentVisit, location.pathname, navigate, setLoadingForContext]
    )
  };
};

export default useMyActionFunctions;
