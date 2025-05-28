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
import { useCallback, useContext, useEffect, useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { v4 as uuid } from 'uuid';

const useMyActionFunctions = () => {
  const { t } = useTranslation();
  const { closeSnackbar } = useSnackbar();
  const { showErrorMessage, showSuccessMessage, showInfoMessage } = useMySnackbar();
  const { dispatchApi } = useMyApi();
  const navigate = useNavigate();
  const location = useLocation();
  const params = useParams();
  const { addListener, removeListener } = useContext(SocketContext);

  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<HowlerSearchResponse<Hit>>(null);
  const [responseQuery, setResponseQuery] = useState('');
  const [progress, setProgress] = useState<[number, number]>([0, 0]);
  const [requestId, setRequestId] = useState<string>(null);
  const [report, setReport] = useState<ActionReport>();

  const handler = useCallback(
    (data: RecievedDataType<{ request_id: string; processed: number; total: number }>) => {
      if (data.type === 'action' && data.request_id === requestId) {
        setProgress([data.processed, data.total]);
      }
    },
    [requestId]
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

      setResponse(_response);
      setResponseQuery(query);
    },
    [dispatchApi]
  );

  useEffect(() => {
    addListener<{ processed: number; total: number }>('action', handler);

    return () => removeListener('action');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [handler]);

  return {
    loading,
    setLoading,
    response,
    setResponse,
    responseQuery,
    report,
    progress,
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
              navigate(`/action/${params.id}`);
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
              navigate(`/action/${newAction.action_id}`);
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
        if (!query) {
          showErrorMessage(t('route.actions.query.empty'));
          return;
        }

        setLoading(true);
        const reqId = uuid();
        setRequestId(reqId);
        setReport(null);

        try {
          setReport(
            await dispatchApi(
              api.action.execute.post({
                request_id: reqId,
                query,
                operations
              }),
              { throwError: false, showError: true }
            )
          );
        } finally {
          setLoading(false);
          setRequestId(null);
          setProgress([0, 0]);
          onSearch(query);
        }
      },
      [dispatchApi, onSearch, showErrorMessage, t]
    ),
    executeAction: useCallback(
      async (actionId: string, query?: string) => {
        setLoading(true);
        const reqId = uuid();
        setRequestId(reqId);
        setReport(null);

        let key: SnackbarKey = null;
        try {
          const action = api.search.action.post({ query: `action_id:${actionId}`, rows: 1 });

          key = showInfoMessage(
            <Stack spacing={1} width="100%" mb={-2} pb={1}>
              <Stack direction="row" spacing={1} px="20px" pt="6px" pb="2px">
                <Terminal fontSize="small" sx={{ mr: 2 }} />
                <span>
                  <Trans i18nKey="actions.running" values={{ action: (await action).items[0]?.name || t('unknown') }} />
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

          setReport(
            await dispatchApi(
              api.action.execute.post({
                request_id: reqId,
                query,
                action_id: actionId
              }),
              { throwError: false, showError: true }
            )
          );

          showSuccessMessage(
            <Trans i18nKey="actions.succeeded" values={{ action: (await action).items[0]?.name || t('unknown') }} />
          );
        } finally {
          if (key) {
            closeSnackbar(key);
          }
          setLoading(false);
          setRequestId(null);
          setProgress([0, 0]);
        }
      },
      [closeSnackbar, dispatchApi, showInfoMessage, showSuccessMessage, t]
    ),
    deleteAction: useCallback(
      async (actionId: string) => {
        setLoading(true);

        try {
          await dispatchApi(api.action.del(actionId));

          if (location.pathname.endsWith(actionId)) {
            navigate('/action');
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
