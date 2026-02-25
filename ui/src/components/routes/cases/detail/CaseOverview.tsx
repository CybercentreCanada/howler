import { Card, CardContent, CardHeader, Divider } from '@mui/material';
import Markdown from 'components/elements/display/Markdown';
import type { Case } from 'models/entities/generated/Case';
import type { FC } from 'react';

const CaseOverview: FC<{ case: Case; updateCase: (_case: Partial<Case>) => Promise<void> }> = ({
  case: _case,
  updateCase
}) => {
  return (
    <Card>
      <CardHeader title={_case.title} subheader={_case.summary} />
      <Divider />
      <CardContent>
        <Markdown md={_case.overview} />
      </CardContent>
    </Card>
  );
};

export default CaseOverview;
