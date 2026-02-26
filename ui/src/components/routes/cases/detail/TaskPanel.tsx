import { Divider, Skeleton, Stack, Typography } from '@mui/material';
import type { Case } from 'models/entities/generated/Case';
import { type FC } from 'react';
import { useTranslation } from 'react-i18next';
import CaseTask from './CaseTask';

const TaskPanel: FC<{ case: Case; updateCase: (_case: Partial<Case>) => Promise<void> }> = ({
  case: _case,
  updateCase
}) => {
  const { t } = useTranslation();

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
          onEdit={newTask =>
            updateCase({
              tasks: _case.tasks.map(_task => {
                if (_task.id !== task.id) {
                  return _task;
                }

                return {
                  ..._task,
                  ...newTask
                };
              })
            })
          }
          onDelete={() => updateCase({ tasks: _case.tasks.filter(_task => _task.id !== task.id) })}
        />
      ))}
    </Stack>
  );
};

export default TaskPanel;
