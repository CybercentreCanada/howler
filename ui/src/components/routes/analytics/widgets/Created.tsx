import { Skeleton } from '@mui/material';
import api from 'api';
import type { HowlerHistogramSearchResponse } from 'api/search/histogram';
import 'chartjs-adapter-dayjs-4';
import useMyChart from 'components/hooks/useMyChart';
import type { Analytic } from 'models/entities/generated/Analytic';
import { forwardRef, useEffect, useRef, useState } from 'react';
import { Line } from 'react-chartjs-2';
import { stringToColor } from 'utils/utils';

const Created = forwardRef<any, { analytic: Analytic }>(({ analytic }, ref) => {
  const { line } = useMyChart();

  const [loading, setLoading] = useState(false);
  const [ingestionData, setIngestionData] = useState<{ [timestamp: string]: number }>({});

  const queryRef = useRef<Promise<HowlerHistogramSearchResponse>>();

  useEffect(() => {
    if (!analytic) {
      return;
    }

    setLoading(true);

    if (!queryRef.current) {
      queryRef.current = api.search.histogram.hit.post('timestamp', {
        query: `howler.analytic:("${analytic.name}")`,
        start: 'now-3M',
        gap: '1d',
        mincount: 0
      });
    }

    queryRef.current
      .then(result => {
        setIngestionData(result);
        queryRef.current = null;
      })
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
