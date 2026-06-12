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
  /** When true all editing controls are hidden and the task is display-only */
  readOnly?: boolean;
  /** If provided, renders an origin chip linking the task back to its source case */
  caseOrigin?: { caseId: string; caseName: string };
}> = ({ task, onEdit, onDelete, paths, newTask = false, readOnly = false, caseOrigin }) => {
  const { t } = useTranslation();

  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState(newTask);

  const [summary, setSummary] = useState(task?.summary || '');
  const [path, setPath] = useState(task?.path ?? null);
  const [assignment, setAssignment] = useState(task?.assignment);
  const [complete, setComplete] = useState(task?.complete ?? false);

  const dirty =
    summary !== task?.summary || path !== task?.path || complete !== task?.complete || assignment !== task?.assignment;

  const onSubmit = async () => {
    if (dirty && editing) {
      setLoading(true);
      await onEdit({ summary, path: !path ? null : path, assignment, complete });
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
      setPath(task.path);
      setComplete(task.complete);
      setAssignment(task.assignment);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [task]);

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

        {!editing && path && <Chip clickable component={Link} to={path} label={path} />}
        {editing && !readOnly && (
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
          disabled={loading || readOnly}
          userIds={[assignment]}
          onChange={([_assigment]) => !readOnly && setAssignment(_assigment)}
          i18nLabel="route.cases.task.set.assignment"
          avatarHeight={24}
        />
        {caseOrigin && (
          <Chip
            size="small"
            component={Link}
            to={`/cases/${caseOrigin.caseId}`}
            clickable
            label={caseOrigin.caseName}
            variant="outlined"
            sx={{ maxWidth: 140 }}
          />
        )}
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
