import { Add, PlayCircleOutline, Save } from '@mui/icons-material';
import {
  Button,
  Card,
  CardContent,
  Checkbox,
  CircularProgress,
  FormControlLabel,
  FormGroup,
  IconButton,
  LinearProgress,
  Stack,
  TextField,
  Tooltip,
  Typography
} from '@mui/material';
import api from 'api';
import { useAppUser } from 'commons/components/app/hooks';
import PageCenter from 'commons/components/pages/PageCenter';
import { FieldContext } from 'components/app/providers/FieldProvider';
import SocketBadge from 'components/elements/display/icons/SocketBadge';
import useMyApi from 'components/hooks/useMyApi';
import HitQuery from 'components/routes/hits/search/HitQuery';
import { difference, uniq } from 'lodash-es';
import type { ActionOperation } from 'models/ActionTypes';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { Action } from 'models/entities/generated/Action';
import type { Operation } from 'models/entities/generated/Operation';
import howlerPluginStore from 'plugins/store';
import { useCallback, useContext, useEffect, useMemo, useState, type ChangeEventHandler, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { usePluginStore } from 'react-pluggable';
import { useLocation, useParams, useSearchParams } from 'react-router-dom';
import { operationReady } from 'utils/actionUtils';
import QueryResultText from '../../../elements/display/QueryResultText';
import ActionReportDisplay from '../shared/ActionReportDisplay';
import OperationEntry from '../shared/OperationEntry';
import useMyActionFunctions from '../useMyActionFunctions';

export interface CustomActionProps {
  operation: ActionOperation;
  operations: ActionOperation[];
  query: string;
  onChange: (operation: Operation) => void;
  onDelete: () => void;
  readonly: boolean;
  values: string;
}

const ActionEditor: FC = () => {
  const { t } = useTranslation();
  const location = useLocation();
  const { dispatchApi } = useMyApi();
  const { getHitFields } = useContext(FieldContext);
  const [searchParams, setSearchParams] = useSearchParams();
  const params = useParams();
  const { user } = useAppUser<HowlerUser>();
  const pluginStore = usePluginStore();

  const { response, loading, setLoading, responseQuery, report, progress, onSearch, saveAction, submitAction } =
    useMyActionFunctions();

  const [operations, setOperations] = useState<ActionOperation[]>([]);
  const [name, setName] = useState('');
  const [userOperations, setUserOperations] = useState<Operation[]>([]);
  const [triggers, setTriggers] = useState<Action['triggers']>([]);

  const availableOperations = useMemo(
    () => operations.filter(o => !userOperations.some(uo => uo.operation_id === o.id)),
    [operations, userOperations]
  );

  const onActionChange = useCallback(
    (index: number) => (a: Operation) => {
      setUserOperations(_userActions => {
        _userActions.splice(index, 1, a);

        return [..._userActions];
      });

      const newOperation = operations.find(op => op.id === a.operation_id);

      setTriggers(triggers.filter(_trigger => newOperation.triggers.includes(_trigger)));
    },
    [operations, triggers]
  );

  const onActionDelete = useCallback(
    (index: number) => () => setUserOperations(_userActions => _userActions.filter((__, _index) => _index !== index)),
    []
  );

  const _submitAction = useCallback(
    () => submitAction(responseQuery, userOperations),
    [responseQuery, submitAction, userOperations]
  );

  const onTriggerChange: ChangeEventHandler<HTMLInputElement> = useCallback(
    async e => {
      if (e.target.checked && !triggers.includes(e.target.name)) {
        setTriggers([...triggers, e.target.name]);
      } else if (!e.target.checked && triggers.includes(e.target.name)) {
        setTriggers(triggers.filter(_t => _t !== e.target.name));
      }
    },
    [triggers]
  );

  useEffect(() => {
    dispatchApi(api.action.operations.get())
      .then(_operations => _operations.filter(a => difference(a.roles, user.roles).length < 1))
      .then(setOperations);

    if (responseQuery) {
      onSearch(responseQuery);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dispatchApi, getHitFields]);

  useEffect(() => {
    if (responseQuery && searchParams.get('query') !== responseQuery) {
      searchParams.set('query', responseQuery);

      setSearchParams(new URLSearchParams(searchParams), { replace: true });
    }
  }, [searchParams, responseQuery, setSearchParams]);

  useEffect(() => {
    if (params.id) {
      setLoading(true);
      dispatchApi(
        api.search.action.post({
          query: `action_id:${params.id}`,
          rows: 1
        }),
        { throwError: false }
      ).then(result => {
        if (!result) {
          setLoading(false);
          return;
        }

        const existingAction = result.items[0];
        setName(existingAction.name);
        searchParams.set('query', existingAction.query);
        setSearchParams(new URLSearchParams(searchParams), { replace: true });
        setUserOperations(existingAction.operations);
        setLoading(false);
        onSearch(existingAction.query);
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dispatchApi, params.id]);

  return (
    <PageCenter maxWidth="1500px" textAlign="left" height="100%">
      <Stack spacing={1}>
        <Stack direction="row" spacing={1}>
          <TextField
            label={t('route.actions.name')}
            size="small"
            disabled={loading}
            value={name}
            onChange={e => setName(e.target.value)}
            fullWidth
          />

          <Button
            variant="outlined"
            size="small"
            startIcon={loading ? <CircularProgress size={16} /> : <Save />}
            sx={{ minWidth: '150px' }}
            disabled={
              !name ||
              loading ||
              userOperations.length < 1 ||
              userOperations.some(
                a =>
                  !operationReady(
                    a?.data_json,
                    operations.find(_a => _a.id === a.operation_id)
                  )
              )
            }
            onClick={() => saveAction(name, responseQuery, userOperations, triggers)}
          >
            {t('route.actions.save')}
          </Button>
        </Stack>

        <FormGroup>
          <Stack direction="row" spacing={1} ml={-1} mr={-1}>
            {uniq(operations.flatMap(op => op.triggers)).map(trigger => {
              const disabled =
                !user.roles.includes('automation_advanced') ||
                userOperations.length < 1 ||
                !userOperations.every(userOperation =>
                  operations.find(operation => operation.id === userOperation.operation_id)?.triggers.includes(trigger)
                );

              const component = (
                <FormControlLabel
                  key={trigger}
                  disabled={disabled}
                  control={
                    <Checkbox
                      sx={{ mr: 0.5 }}
                      name={trigger}
                      onChange={onTriggerChange}
                      checked={triggers?.includes(trigger) ?? false}
                    />
                  }
                  label={t(`route.actions.trigger.${trigger}`)}
                />
              );

              return (
                <Tooltip
                  key={trigger}
                  title={
                    !user.roles.includes('automation_advanced')
                      ? t('route.actions.trigger.disabled.permissions')
                      : disabled && userOperations.length > 0
                        ? t('route.actions.trigger.disabled.explanation')
                        : null
                  }
                >
                  {component}
                </Tooltip>
              );
            })}
          </Stack>
        </FormGroup>
        <Stack direction="row" justifyContent="space-between" alignItems="end" sx={{ mb: -1 }}>
          <Typography
            sx={theme => ({ color: theme.palette.text.disabled, fontStyle: 'italic', mb: 0.5 })}
            variant="body2"
          >
            {t('hit.search.prompt')}
          </Typography>
          <SocketBadge size="small" />
        </Stack>
        <HitQuery triggerSearch={onSearch} />
        {response ? (
          <QueryResultText count={response.total} query={responseQuery} />
        ) : (
          <Typography
            sx={theme => ({
              color: theme.palette.text.secondary,
              fontSize: '0.9em',
              fontStyle: 'italic',
              mb: 0.5,
              '& a': { color: theme.palette.text.secondary }
            })}
            variant="body2"
          >
            {t('route.actions.search.warning')}
          </Typography>
        )}
        {loading &&
          (progress[1] > 0 ? (
            <LinearProgress
              variant="determinate"
              value={(progress[0] / progress[1]) * 100}
              valueBuffer={((progress[0] + 10) / progress[1]) * 100}
            />
          ) : (
            <LinearProgress />
          ))}
        {report && <ActionReportDisplay report={report} operations={operations} />}
      </Stack>
      {operations.length > 0 && (
        <Stack spacing={1} mt={1}>
          {userOperations.map((a, index) => {
            const operation = operations.find(_operation => _operation.id === a.operation_id);

            if (howlerPluginStore.operations.includes(a.operation_id)) {
              return pluginStore.executeFunction(`operation.${a.operation_id}`, {
                operation,
                operations: [operation, ...availableOperations],
                query: responseQuery,
                onChange: onActionChange(index),
                onDelete: onActionDelete(index),
                values: a.data_json
              } as CustomActionProps);
            }

            return (
              <OperationEntry
                key={a.operation_id}
                query={responseQuery}
                operation={operation}
                operations={[operation, ...availableOperations]}
                values={a.data_json}
                onChange={onActionChange(index)}
                onDelete={onActionDelete(index)}
              />
            );
          })}

          {userOperations.length < operations.length && (
            <Card variant="outlined" sx={{ flex: 1 }}>
              <CardContent sx={{ paddingBottom: '16px !important' }}>
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                  <Typography variant="body1" color={!response && 'text.secondary'}>
                    {t('route.actions.operation.add')}
                  </Typography>
                  <IconButton
                    size="small"
                    disabled={!response}
                    onClick={() =>
                      setUserOperations(_userActions => [
                        ..._userActions,
                        {
                          operation_id: operations.find(a => !_userActions.some(_a => _a.operation_id === a.id)).id,
                          data_json: '{}'
                        }
                      ])
                    }
                  >
                    <Add />
                  </IconButton>
                </Stack>
              </CardContent>
            </Card>
          )}

          {operations.length > 0 && !location.pathname.endsWith('/edit') && (
            <Button
              variant="outlined"
              color="success"
              sx={{ alignSelf: 'start' }}
              startIcon={loading ? <CircularProgress size={16} /> : <PlayCircleOutline />}
              disabled={
                !responseQuery ||
                !response ||
                loading ||
                userOperations.length < 1 ||
                userOperations.some(
                  a =>
                    !operationReady(
                      a?.data_json,
                      operations.find(_a => _a.id === a.operation_id)
                    )
                )
              }
              onClick={_submitAction}
            >
              {t('route.actions.execute')}
            </Button>
          )}
        </Stack>
      )}
    </PageCenter>
  );
};

export default ActionEditor;
