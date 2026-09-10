import { useTheme } from '@mui/material';
import 'chartjs-adapter-dayjs-4';
import type { Analytic } from 'models/entities/generated/Analytic';
import { forwardRef } from 'react';
import { getStatusColor } from 'utils/utils';
import Stacked from './Stacked';

const Status = forwardRef<any, { analytic: Analytic }>(({ analytic }, ref) => {
  const theme = useTheme();

  return (
    <Stacked
      ref={ref as any}
      analytic={analytic}
      field="howler.status"
      color={status => getStatusColor(status, theme.palette.grey[500], theme)}
    />
  );
});

export default Status;
