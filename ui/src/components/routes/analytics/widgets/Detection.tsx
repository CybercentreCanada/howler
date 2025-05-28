import 'chartjs-adapter-moment';
import type { Analytic } from 'models/entities/generated/Analytic';
import { forwardRef } from 'react';
import { stringToColor } from 'utils/utils';
import Stacked from './Stacked';

const Detection = forwardRef<any, { analytic: Analytic; maxWidth?: string }>(({ analytic }, ref) => {
  return <Stacked ref={ref as any} analytic={analytic} field="howler.detection" color={stringToColor} />;
});

export default Detection;
