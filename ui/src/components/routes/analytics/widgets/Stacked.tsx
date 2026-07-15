import { Skeleton } from '@mui/material';
import api from 'api';
import type { ChartDataset, ChartOptions } from 'chart.js';
import 'chartjs-adapter-dayjs-4';
import useMyChart from 'components/hooks/useMyChart';
import sum from 'lodash-es/sum';
import type { Analytic } from 'models/entities/generated/Analytic';
import { forwardRef, useCallback, useEffect, useMemo, useState } from 'react';
import { Line } from 'react-chartjs-2';

const Stacked = forwardRef<
  any,
  {
    analytic: Analytic;
    field: string;
    color?: (value: string) => string;
  }
>(({ analytic, field, color }, ref) => {
  const { line } = useMyChart();

  const [loading, setLoading] = useState(false);
  const [datasets, setDatasets] = useState<ChartDataset<'line'>[]>([]);

  const fetchData = useCallback(async () => {
    if (loading) {
      return;
    }

    try {
      setLoading(true);

      const result = await api.search.facet.hit.post({
        query: `howler.analytic:("${analytic.name}")`,
        fields: [field]
      });

      const values = Object.entries(result[field])
        .sort(([__, valA], [___, valB]) => valB - valA)
        .map(([key]) => key);

      setDatasets(
        await Promise.all(
          values.map(async _value => {
            const ingestionData = await api.search.histogram.hit.post('timestamp', {
              query: `howler.analytic:("${analytic.name}") AND ${field}:("${_value}")`,
              start: 'now-3M',
              gap: '1d',
              mincount: 0
            });

            return {
              label: _value,
              fill: true,
              data: Object.keys(ingestionData).map((time, index, arr) => ({
                x: new Date(time).getTime(),
                y: sum(arr.map(key => ingestionData[key]).slice(0, index))
              })),
              borderColor: color(_value),
              backgroundColor: color(_value),
              pointBackgroundColor: 'transparent',
              pointBorderWidth: 0
            };
          })
        )
      );
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analytic?.name, color, field]);

  useEffect(() => {
    if (!analytic) {
      return;
    }

    fetchData();
  }, [analytic, fetchData]);

  const options: ChartOptions<'line'> = useMemo(() => {
    const baseOptions = line(`route.analytics.${field.replace('howler.', '')}.title`);

    return {
      ...baseOptions,
      plugins: {
        ...baseOptions.plugins,
        tooltip: {
          mode: 'index'
        }
      },
      scales: {
        ...baseOptions.scales,
        y: {
          ...baseOptions.scales.y,
          stacked: true
        }
      }
    };
  }, [field, line]);

  return analytic && !loading ? (
    <Line
      ref={ref as any}
      options={options}
      data={{
        datasets
      }}
    />
  ) : (
    <Skeleton variant="rounded" height={200} />
  );
});

export default Stacked;
