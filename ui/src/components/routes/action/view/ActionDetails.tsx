import { Delete, Edit, PersonAdd, PlayCircleOutline, Search } from '@mui/icons-material';
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
import { PageCenter, useAppUser } from '@tui/core';
import api from 'api';
import { ModalContext } from 'components/app/providers/ModalProvider';
import FlexOne from 'components/elements/addons/layout/FlexOne';
import Phrase from 'components/elements/addons/search/phrase/Phrase';
import HowlerAvatar from 'components/elements/display/HowlerAvatar';
import { MembershipManagement } from 'components/elements/MembershipManagement';
import useMyApi from 'components/hooks/useMyApi';
import useMySnackbar from 'components/hooks/useMySnackbar';
import OperationEntry from 'components/routes/action/shared/OperationEntry';
import type { ActionOperation } from 'models/ActionTypes';
import type { Action } from 'models/entities/generated/Action';
import type { HowlerUser } from 'models/entities/HowlerUser';
import howlerPluginStore from 'plugins/store';
import { useCallback, useContext, useEffect, useState, type ChangeEventHandler } from 'react';
import { useTranslation } from 'react-i18next';
import { usePluginStore } from 'react-pluggable';
import { Link, useParams } from 'react-router';
import QueryResultText from '../../../elements/display/QueryResultText';
import type { CustomActionProps } from '../edit/ActionEditor';
import ActionReportDisplay from '../shared/ActionReportDisplay';
import useMyActionFunctions from '../useMyActionFunctions';

const ActionDetails = () => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const params = useParams();
  const { user } = useAppUser<HowlerUser>();
  const pluginStore = usePluginStore();

  const { response, onSearch, loading, setLoading, executeAction, deleteAction, progress, report } =
    useMyActionFunctions();

  const [operations, setOperations] = useState<ActionOperation[]>([]);
  const [action, setAction] = useState<Action>();
  const [memberModalOpen, setMemberModalOpen] = useState(false);

  const { withConfirmDeleteModal } = useContext(ModalContext);
  const { showSuccessMessage } = useMySnackbar();

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

  const onDelete = useCallback(
    () =>
      withConfirmDeleteModal(async () => {
        await deleteAction(action?.action_id);
        showSuccessMessage(t('route.actions.manager.delete.success'));
      }),
    [withConfirmDeleteModal, deleteAction, action?.action_id, showSuccessMessage, t]
  );

  useEffect(() => {
    setLoading(true);

    void Promise.all([
      dispatchApi(api.action.operations.get()).then(setOperations),
      dispatchApi(api.action.get(params.id).then(setAction))
    ]).finally(() => setLoading(false));
  }, [dispatchApi, params.id, setLoading]);

  useEffect(() => {
    if (action?.query) {
      void onSearch(action?.query);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [action?.query]);

  const editRoles = user.roles.includes('automation_basic') || user.roles.includes('automation_advanced');
  const execRoles =
    editRoles ||
    user.roles.includes('admin') ||
    user.roles.includes('actionrunner_basic') ||
    user.roles.includes('actionrunner_advanced');
  const adminList = action?.admins ?? [];

  return (
    <PageCenter maxWidth="1500px" textAlign="left" height="100%">
      <Stack spacing={1}>
        <Stack direction="row" justifyContent="space-between">
          <Typography variant="h5">{action?.name}</Typography>
          {action?.owner && <HowlerAvatar sx={{ width: 32, height: 32 }} userId={action.owner} />}
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
          {((action?.owner === user.username && editRoles) || user.roles?.includes('admin')) && (
            <Button startIcon={<Delete />} size="small" variant="outlined" color="error" onClick={onDelete}>
              {t('button.delete')}
            </Button>
          )}
          {execRoles && (
            <Button
              startIcon={<PlayCircleOutline />}
              size="small"
              variant="outlined"
              color="success"
              onClick={() => executeAction(action?.action_id)}
            >
              {t('route.actions.execute')}
            </Button>
          )}
          {((action?.owner === user.username && editRoles) ||
            (adminList.includes(user.username) && editRoles) ||
            (action?.members?.includes(user.username) && editRoles) ||
            user.roles?.includes('admin')) && (
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
          {(action?.owner === user.username || adminList.includes(user.username) || user.roles?.includes('admin')) && (
            <Button startIcon={<PersonAdd />} size="small" variant="outlined" onClick={() => setMemberModalOpen(true)}>
              {t('membership.manage')}
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
            if (howlerPluginStore.operations.includes(a.operation_id)) {
              return pluginStore.executeFunction(`operation.${a.operation_id}`, {
                readonly: true,
                operation: operations.find(_operation => _operation.id === a.operation_id),
                operations,
                query: action.query,
                values: a.data_json
              } as CustomActionProps);
            }

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
      <MembershipManagement open={memberModalOpen} onClose={() => setMemberModalOpen(false)} />
    </PageCenter>
  );
};

export default ActionDetails;
