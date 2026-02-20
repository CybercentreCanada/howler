import { Card, Checkbox, Chip, Stack, Typography } from '@mui/material';
import HowlerAvatar from 'components/elements/display/HowlerAvatar';
import type { Task } from 'models/entities/generated/Task';
import type { FC } from 'react';
import { Link } from 'react-router-dom';

const CaseTask: FC<{ caseId: string; task: Task }> = ({ task }) => {
  return (
    <Card key={task.id} sx={{ pl: 0.5, pr: 1, py: 0.5 }}>
      <Stack direction="row" alignItems="center" spacing={1}>
        <Checkbox color="success" checked={task.complete} size="small" />
        <Typography sx={[task.complete && { textDecoration: 'line-through' }]}>{task.summary}</Typography>
        {task.path && <Chip size="small" clickable component={Link} to={task.path} label={task.path} />}
        {task.assignment && <HowlerAvatar sx={{ height: 24, width: 24 }} userId={task.assignment} />}
      </Stack>
    </Card>
  );
};

export default CaseTask;
