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
import type { Task } from 'models/entities/generated/Task';
import { useEffect, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

const CaseTask: FC<{
  task?: Task;
  paths: string[];
  onDelete?: () => Promise<void>;
  onEdit: (task?: Partial<Task>) => Promise<void>;
  loading?: boolean;
  newTask?: boolean;
}> = ({ task, onEdit, onDelete, paths, newTask = false }) => {
  const { t } = useTranslation();

  const [editing, setEditing] = useState(newTask);
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState(task?.summary || '');
  const [path, setPath] = useState(task?.path ?? null);
  const [assignment, setAssignment] = useState(task?.assignment);
  const [complete, setComplete] = useState(task?.complete ?? false);

  const dirty = summary !== task?.summary || path !== task?.path;

  const onSubmit = async () => {
    if (dirty && editing) {
      console.log('confirmed bongo time');
      setLoading(true);
      await onEdit({ summary, path: !path ? null : path, assignment });
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!editing && task?.assignment !== assignment) {
      console.log('confirmed bongo time 2');
      setLoading(true);
      onEdit({ assignment }).finally(() => setLoading(false));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assignment]);

  useEffect(() => {
    if (!editing && task?.complete !== complete) {
      console.log('confirmed bongo time 3');
      setLoading(true);
      onEdit({ complete }).finally(() => setLoading(false));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [complete]);

  return (
    <Card sx={{ pl: 0.5, pr: 1, py: 0.5, position: 'relative' }}>
      <Stack direction="row" alignItems="center" spacing={1}>
        <Checkbox
          disabled={loading}
          color="success"
          checked={complete}
          size="small"
          onChange={(_ev, _complete) => setComplete(_complete)}
        />
        {editing ? (
          <TextField
            disabled={loading}
            value={summary}
            onChange={e => setSummary(e.target.value)}
            size="small"
            fullWidth
            sx={{ minWidth: '40%' }}
          />
        ) : (
          <Typography sx={[task?.complete && { textDecoration: 'line-through' }]}>
            {task?.summary || summary}
          </Typography>
        )}

        {!editing && task?.path && <Chip clickable component={Link} to={task.path} label={task.path} />}
        {editing && (
          <Autocomplete
            disabled={loading}
            value={path}
            options={paths}
            onChange={(_ev, value) => setPath(value)}
            fullWidth
            renderInput={params => <TextField {...params} size="small" />}
          />
        )}
        <UserList
          disabled={loading}
          userIds={[assignment]}
          onChange={([_assigment]) => setAssignment(_assigment)}
          i18nLabel="route.cases.task.set.assignment"
          avatarHeight={24}
        />
        <div style={{ flex: 1 }} />
        {editing && (
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
        {editing && (
          <Tooltip title={t('route.cases.task.edit.cancel')}>
            <IconButton size="small" onClick={() => setEditing(false)} disabled={loading}>
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
