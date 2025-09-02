import { Skeleton, useTheme } from '@mui/material';
import api from 'api';
import type { HowlerFacetSearchResponse } from 'api/search/facet';
import 'chartjs-adapter-dayjs-4';
import useMyChart from 'components/hooks/useMyChart';
import type { Analytic } from 'models/entities/generated/Analytic';
import { forwardRef, useEffect, useMemo, useState } from 'react';
import { Doughnut } from 'react-chartjs-2';
import { ESCALATION_COLORS } from 'utils/constants';

const Escalation = forwardRef<any, { analytic: Analytic; maxWidth?: string }>(({ analytic, maxWidth = '45%' }, ref) => {
  const theme = useTheme();
  const { doughnut } = useMyChart();

  const [loading, setLoading] = useState(false);
  const [escalationData, setEscalationData] = useState<HowlerFacetSearchResponse>({});

  const escalationColors = useMemo(
    () =>
      Object.keys(escalationData).map(e =>
        ESCALATION_COLORS[e] ? theme.palette[ESCALATION_COLORS[e]].main : 'rgba(255, 255, 255, 0.16)'
      ),
    [escalationData, theme.palette]
  );

  useEffect(() => {
    if (!analytic) {
      return;
    }

    setLoading(true);

    api.search.facet.hit
      .post({
        query: `howler.analytic:("${analytic.name}")`,
        fields: ['howler.escalation']
      })
      .then(data => setEscalationData(data['howler.escalation']))
      .finally(() => setLoading(false));
  }, [analytic]);

  return analytic && !loading ? (
    <div style={{ maxWidth }}>
      <Doughnut
        ref={ref as any}
        options={doughnut('route.analytics.escalation.title', '')}
        data={{
          labels: Object.keys(escalationData),
          datasets: [
            {
              label: analytic?.name,
              data: Object.values(escalationData),
              borderColor: escalationColors,
              backgroundColor: escalationColors
            }
          ]
        }}
      />
    </div>
  ) : (
    <Skeleton variant="rounded" height={200} width="45%" />
  );
});

export default Escalation;
