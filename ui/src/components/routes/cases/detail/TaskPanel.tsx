import { Divider, Stack, Typography } from '@mui/material';
import type { Case } from 'models/entities/generated/Case';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';
import CaseTask from './CaseTask';

const TaskPanel: FC<{ case: Case }> = ({ case: _case }) => {
  const { t } = useTranslation();

  // TODO: Implement adding tasks, checking tasks off, etc.

  return (
    <Stack spacing={1}>
      <Typography flex={1} variant="h4">
        {t('page.cases.dashboard.tasks')}
      </Typography>
      <Divider />
      {_case.tasks.map(task => (
        <CaseTask key={task.id} caseId={_case.case_id} task={task} />
      ))}
    </Stack>
  );
};

export default TaskPanel;
