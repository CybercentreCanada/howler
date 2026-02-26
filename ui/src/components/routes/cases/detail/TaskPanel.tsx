import { Add } from '@mui/icons-material';
import { Divider, Skeleton, Stack, Typography } from '@mui/material';
import type { Case } from 'models/entities/generated/Case';
import type { Task } from 'models/entities/generated/Task';
import { useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import CaseTask from './CaseTask';

const TaskPanel: FC<{ case: Case; updateCase: (_case: Partial<Case>) => Promise<void> }> = ({
  case: _case,
  updateCase
}) => {
  const { t } = useTranslation();

  const [addingTask, setAddingTask] = useState(false);

  const onEdit = (task?: Task) => async (newTask: Partial<Task>) => {
    if (task) {
      await updateCase({
        tasks: _case.tasks.map(_task => {
          if (_task.id !== task.id) {
            return _task;
          }

          return {
            ..._task,
            ...newTask
          };
        })
      });
    } else {
      await updateCase({
        tasks: [..._case.tasks, newTask]
      });
    }
  };

  if (!_case) {
    return <Skeleton height={240} />;
  }

  return (
    <Stack spacing={1}>
      <Typography flex={1} variant="h4">
        {t('page.cases.dashboard.tasks')}
      </Typography>
      <Divider />
      {_case.tasks.map(task => (
        <CaseTask
          key={task.id}
          task={task}
          paths={_case.items.map(item => item.path)}
          onEdit={onEdit(task)}
          onDelete={() => updateCase({ tasks: _case.tasks.filter(_task => _task.id !== task.id) })}
        />
      ))}
      {addingTask && (
        <CaseTask
          newTask
          paths={_case.items.map(item => item.path)}
          onEdit={async task => {
            await onEdit()(task);

            setAddingTask(false);
          }}
          onDelete={async () => setAddingTask(false)}
        />
      )}
      <Stack
        onClick={() => setAddingTask(true)}
        direction="row"
        spacing={2}
        sx={theme => ({
          borderStyle: 'dashed',
          borderColor: theme.palette.text.secondary,
          borderWidth: '0.15rem',
          borderRadius: '0.15rem',
          opacity: 0.3,
          justifyContent: 'center',
          alignItems: 'center',
          padding: 1,
          transition: theme.transitions.create('opacity'),
          '&:hover': {
            opacity: 1,
            cursor: 'pointer'
          }
        })}
      >
        <Add />
        <Typography>{t('page.cases.dashboard.tasks.add')}</Typography>
      </Stack>
    </Stack>
  );
};

export default TaskPanel;
