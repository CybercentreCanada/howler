import { useTheme } from '@mui/material';
import 'chartjs-adapter-moment';
import type { Analytic } from 'models/entities/generated/Analytic';
import { forwardRef } from 'react';
import { STATUS_COLORS } from 'utils/constants';
import Stacked from './Stacked';

const Status = forwardRef<any, { analytic: Analytic }>(({ analytic }, ref) => {
  const theme = useTheme();

  return (
    <Stacked
      ref={ref as any}
      analytic={analytic}
      field="howler.status"
      color={status => (status === 'on-hold' ? theme.palette.grey : theme.palette[STATUS_COLORS[status]].main)}
    />
  );
});

export default Status;
