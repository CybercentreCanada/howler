import { Check, Close, Delete, Edit } from '@mui/icons-material';
import {
  Autocomplete,
  Card,
  Checkbox,
  Chip,
  IconButton,
  LinearProgress,
  Stack,
  TextField,
  Tooltip,
  Typography
} from '@mui/material';
import UserList from 'components/elements/UserList';
import type { Case } from 'models/entities/generated/Case';
import type { Item } from 'models/entities/generated/Item';
import type { Task } from 'models/entities/generated/Task';
import { useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { buildPathFromID } from '../utils';

const CaseTask: FC<{
  case: Case;
  task?: Task;
  onDelete?: () => Promise<void>;
  onEdit?: (task?: Partial<Task>) => Promise<void>;
  loading?: boolean;
  newTask?: boolean;
  /** When true all editing controls are hidden and the task is display-only */
  readOnly?: boolean;
}> = ({ case: _case, task, onEdit, onDelete, newTask = false, readOnly = false }) => {
  const { t } = useTranslation();

  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState(newTask);

  const [summary, setSummary] = useState(task?.summary || '');
  const [item, setItem] = useState(task?.item ? _case?.items.find(_item => _item.id === task.item) : null);
  const [assignment, setAssignment] = useState(task?.assignment);
  const [complete, setComplete] = useState(task?.complete ?? false);

  const dirty =
    summary !== task?.summary || item.id !== task?.item || complete !== task?.complete || assignment !== task?.assignment;

  const options: Item[] = useMemo(() => _case?.items ?? [], [_case]);

  const onSubmit = async () => {
    if (dirty && editing) {
      setLoading(true);
      await onEdit({ summary, item: !item ? null : item.id, assignment, complete });
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!readOnly && !editing && task?.assignment !== assignment) {
      setLoading(true);
      onEdit({ assignment }).finally(() => setLoading(false));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assignment]);

  useEffect(() => {
    if (!readOnly && !editing && task?.complete !== complete) {
      setLoading(true);
      onEdit({ complete }).finally(() => setLoading(false));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [complete]);

  useEffect(() => {
    if (!editing && task) {
      setSummary(task.summary);
      setItem(task?.item ? _case?.items.find(_item => _item.id === task.item) : null);
      setComplete(task.complete);
      setAssignment(task.assignment);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [task, _case]);

  return (
    <Card sx={{ pl: 0.5, pr: 1, py: 0.5, position: 'relative' }}>
      <Stack direction="row" alignItems="center" spacing={1}>
        <Checkbox
          disabled={loading || readOnly}
          color="success"
          checked={complete}
          size="small"
          onChange={(_ev, _complete) => !readOnly && setComplete(_complete)}
        />
        {editing && !readOnly ? (
          <TextField
            disabled={loading}
            value={summary}
            onChange={e => setSummary(e.target.value)}
            size="small"
            fullWidth
            sx={{ minWidth: '40%' }}
          />
        ) : (
          <Typography sx={[complete && { textDecoration: 'line-through' }]}>{task?.summary || summary}</Typography>
        )}

        {!editing && item && <Chip clickable component={Link} to={buildPathFromID(_case, item.id)} label={item.name} />}
        {editing && !readOnly && (
          <Autocomplete
            disabled={loading}
            value={item}
            options={options}
            getOptionLabel={opt => buildPathFromID(_case, opt.id)}
            isOptionEqualToValue={opt => opt.id === item.id}
            onChange={(_ev, value) => setItem(value)}
            fullWidth
            renderInput={params => <TextField {...params} size="small" />}
          />
        )}
        <UserList
          disabled={loading || readOnly}
          userIds={[assignment]}
          onChange={([_assigment]) => !readOnly && setAssignment(_assigment)}
          i18nLabel="route.cases.task.set.assignment"
          avatarHeight={24}
        />
        <div style={{ flex: 1 }} />
        {!readOnly && editing && !newTask && (
          <Tooltip title={t('route.cases.task.delete')}>
            <IconButton
              size="small"
              color="error"
              onClick={() => {
                setLoading(true);
                onDelete().then(() => setLoading(false));
              }}
              disabled={loading}
            >
              <Delete fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
        {!readOnly && (
          <Tooltip title={t(editing ? 'route.cases.task.edit.save' : 'route.cases.task.edit')}>
            <span>
              <IconButton
                size="small"
                color={editing ? 'success' : 'default'}
                onClick={async () => {
                  if (!editing) {
                    setEditing(true);
                    return;
                  }

                  await onSubmit();
                  setEditing(false);
                }}
                disabled={(!dirty && editing) || loading || !summary}
              >
                {editing ? <Check fontSize="small" /> : <Edit fontSize="small" />}
              </IconButton>
            </span>
          </Tooltip>
        )}
        {!readOnly && editing && (
          <Tooltip title={t('route.cases.task.edit.cancel')}>
            <IconButton
              size="small"
              onClick={() => {
                if (newTask) {
                  onDelete();
                } else {
                  setEditing(false);
                }
              }}
              disabled={loading}
            >
              <Close fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
      </Stack>
      {loading && <LinearProgress sx={{ left: 0, bottom: 0, right: 0, position: 'absolute' }} />}
    </Card>
  );
};

export default CaseTask;
