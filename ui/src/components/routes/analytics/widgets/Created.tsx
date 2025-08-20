import { Skeleton } from '@mui/material';
import api from 'api';
import 'chartjs-adapter-dayjs';
import useMyChart from 'components/hooks/useMyChart';
import type { Analytic } from 'models/entities/generated/Analytic';
import { forwardRef, useEffect, useState } from 'react';
import { Line } from 'react-chartjs-2';
import { stringToColor } from 'utils/utils';

const Created = forwardRef<any, { analytic: Analytic }>(({ analytic }, ref) => {
  const { line } = useMyChart();

  const [loading, setLoading] = useState(false);
  const [ingestionData, setIngestionData] = useState<{ [timestamp: string]: number }>({});

  useEffect(() => {
    if (!analytic) {
      return;
    }

    setLoading(true);

    api.search.histogram.hit
      .post('timestamp', {
        query: `howler.analytic:("${analytic.name}")`,
        start: 'now-3M',
        gap: '1d',
        mincount: 0
      })
      .then(setIngestionData)
      .finally(() => setLoading(false));
  }, [analytic]);

  return analytic && !loading ? (
    <Line
      ref={ref as any}
      options={line('route.analytics.ingestion.title') as any}
      data={{
        datasets: [
          {
            label: analytic?.name,
            data: Object.keys(ingestionData).map(time => ({
              x: new Date(time).getTime(),
              y: ingestionData[time]
            })),
            borderColor: stringToColor(analytic?.name),
            backgroundColor: 'transparent',
            pointBackgroundColor: Object.keys(ingestionData).map(time =>
              ingestionData[time] ? stringToColor(analytic?.name) : 'transparent'
            ),
            pointBorderWidth: Object.keys(ingestionData).map(time => (ingestionData[time] ? 2 : 0))
          }
        ]
      }}
    />
  ) : (
    <Skeleton variant="rounded" height={200} />
  );
});

export default Created;
