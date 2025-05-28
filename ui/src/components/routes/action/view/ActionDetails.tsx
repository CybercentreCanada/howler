import { Delete, Edit, PlayCircleOutline, Search } from '@mui/icons-material';
import {
  Button,
  Checkbox,
  FormControlLabel,
  FormGroup,
  IconButton,
  LinearProgress,
  Stack,
  Typography
} from '@mui/material';
import api from 'api';
import { useAppUser } from 'commons/components/app/hooks';
import PageCenter from 'commons/components/pages/PageCenter';
import FlexOne from 'components/elements/addons/layout/FlexOne';
import Phrase from 'components/elements/addons/search/phrase/Phrase';
import HowlerAvatar from 'components/elements/display/HowlerAvatar';
import useMyApi from 'components/hooks/useMyApi';
import OperationEntry from 'components/routes/action/shared/OperationEntry';
import type { ActionOperation } from 'models/ActionTypes';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { Action } from 'models/entities/generated/Action';
import { useCallback, useEffect, useState, type ChangeEventHandler } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import QueryResultText from '../../../elements/display/QueryResultText';
import ActionReportDisplay from '../shared/ActionReportDisplay';
import useMyActionFunctions from '../useMyActionFunctions';

const ActionDetails = () => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const params = useParams();
  const { user } = useAppUser<HowlerUser>();

  const { response, onSearch, loading, setLoading, executeAction, deleteAction, progress, report } =
    useMyActionFunctions();

  const [operations, setOperations] = useState<ActionOperation[]>([]);
  const [action, setAction] = useState<Action>();

  const onTriggerChange: ChangeEventHandler<HTMLInputElement> = useCallback(
    async e => {
      let newTriggers = action.triggers ?? [];

      if (e.target.checked && !newTriggers.includes(e.target.name)) {
        newTriggers.push(e.target.name);
      } else if (!e.target.checked && newTriggers.includes(e.target.name)) {
        newTriggers = newTriggers.filter(_t => _t !== e.target.name);
      }

      setLoading(true);

      try {
        await dispatchApi(
          api.action.patch(action.action_id, {
            triggers: newTriggers
          })
        );

        setAction({ ...action, triggers: newTriggers });
      } finally {
        setLoading(false);
      }
    },
    [action, dispatchApi, setLoading]
  );

  useEffect(() => {
    setLoading(true);

    Promise.all([
      dispatchApi(api.action.operations.get()).then(setOperations),
      dispatchApi(api.action.get(params.id).then(setAction))
    ]).finally(() => setLoading(false));
  }, [dispatchApi, params.id, setLoading]);

  useEffect(() => {
    if (action?.query) {
      onSearch(action?.query);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [action?.query]);

  return (
    <PageCenter maxWidth="1500px" textAlign="left" height="100%">
      <Stack spacing={1}>
        <Stack direction="row" justifyContent="space-between">
          <Typography variant="h5">{action?.name}</Typography>
          {action?.owner_id && <HowlerAvatar sx={{ width: 32, height: 32 }} userId={action.owner_id} />}
        </Stack>
        <Phrase
          fullWidth
          value={action?.query}
          disabled
          size="small"
          onChange={() => {}}
          startAdornment={
            <IconButton onClick={() => onSearch(action?.query)}>
              <Search fontSize="small" />
            </IconButton>
          }
        />
        <Stack direction="row" alignItems="center" spacing={1}>
          {response && <QueryResultText count={response.total} query={action?.query} />}
          <FlexOne />
          {(action?.owner_id === user.username || user.roles?.includes('admin')) && (
            <Button
              startIcon={<Delete />}
              size="small"
              variant="outlined"
              color="error"
              onClick={() => deleteAction(action?.action_id)}
            >
              {t('delete')}
            </Button>
          )}
          <Button
            startIcon={<PlayCircleOutline />}
            size="small"
            variant="outlined"
            color="success"
            onClick={() => executeAction(action?.action_id)}
          >
            {t('route.actions.execute')}
          </Button>
          {(action?.owner_id === user.username || user.roles?.includes('admin')) && (
            <Button
              startIcon={<Edit />}
              size="small"
              variant="outlined"
              component={Link}
              to={`/action/${params.id}/edit`}
            >
              {t('route.actions.edit')}
            </Button>
          )}
        </Stack>
        {user.roles.includes('automation_advanced') && (
          <FormGroup>
            <Stack direction="row" spacing={1}>
              {action?.operations
                ?.map(a => (operations ?? []).find(_action => _action.id === a.operation_id)?.triggers ?? [])
                .reduce((acc, triggers) => acc.filter(_t => triggers.includes(_t)))
                .map(trigger => (
                  <FormControlLabel
                    key={trigger}
                    control={
                      <Checkbox
                        name={trigger}
                        onChange={onTriggerChange}
                        checked={action?.triggers?.includes(trigger) ?? false}
                      />
                    }
                    label={t(`route.actions.trigger.${trigger}`)}
                  />
                ))}
            </Stack>
          </FormGroup>
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
        {operations.length > 0 &&
          action &&
          action.operations.map(a => {
            return (
              <OperationEntry
                key={a.operation_id}
                readonly
                operations={operations}
                query={action.query}
                values={a.data_json}
                operation={operations.find(_operation => _operation.id === a.operation_id)}
              />
            );
          })}
      </Stack>
    </PageCenter>
  );
};

export default ActionDetails;
