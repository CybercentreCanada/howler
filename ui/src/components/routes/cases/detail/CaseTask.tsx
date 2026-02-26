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
import { useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

const CaseTask: FC<{
  task: Task;
  paths: string[];
  onDelete: () => void;
  onEdit: (task: Partial<Task>) => Promise<void>;
  loading?: boolean;
}> = ({ task, onEdit, onDelete, paths }) => {
  const { t } = useTranslation();

  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState(task.summary);
  const [path, setPath] = useState(task.path);

  const dirty = summary !== task.summary || path !== task.path;

  const onOwnerChange = async ([assignment]: string[]) => {
    setLoading(true);
    await onEdit({
      assignment
    });
    setLoading(false);
  };

  const onSubmit = async () => {
    if (dirty) {
      setLoading(true);
      await onEdit({ summary, path: !path ? null : path });
      setLoading(false);
    }
  };

  return (
    <Card key={task.id} sx={{ pl: 0.5, pr: 1, py: 0.5, position: 'relative' }}>
      <Stack direction="row" alignItems="center" spacing={1}>
        <Checkbox
          disabled={loading}
          color="success"
          checked={task.complete}
          size="small"
          onChange={async (_ev, complete) => {
            try {
              setLoading(true);
              await onEdit({ complete });
            } finally {
              setLoading(false);
            }
          }}
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
          <Typography sx={[task.complete && { textDecoration: 'line-through' }]}>{task.summary}</Typography>
        )}

        {task.path && !editing && <Chip clickable component={Link} to={task.path} label={task.path} />}
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
        {task.assignment && (
          <UserList
            disabled={loading}
            userIds={[task.assignment]}
            onChange={onOwnerChange}
            i18nLabel="route.cases.task.set.assignment"
            avatarHeight={24}
          />
        )}
        <div style={{ flex: 1 }} />
        {editing && (
          <Tooltip title={t('route.cases.task.delete')}>
            <IconButton size="small" color="error" onClick={onDelete}>
              <Delete fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
        <Tooltip title={t(editing ? 'route.cases.task.edit.save' : 'route.cases.task.edit')}>
          <IconButton
            size="small"
            color={editing ? 'success' : 'default'}
            onClick={() => {
              if (!editing) {
                setEditing(true);
                return;
              }

              setEditing(false);
              onSubmit();
            }}
            disabled={(!dirty && editing) || loading}
          >
            {editing ? <Check fontSize="small" /> : <Edit fontSize="small" />}
          </IconButton>
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
