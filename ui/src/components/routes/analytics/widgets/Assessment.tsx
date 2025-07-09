import { Box, Skeleton, Typography } from '@mui/material';
import api from 'api';
import type { HowlerFacetSearchResponse } from 'api/search/facet';
import 'chartjs-adapter-moment';
import useMyChart from 'components/hooks/useMyChart';
import type { Analytic } from 'models/entities/generated/Analytic';
import { forwardRef, useEffect, useState } from 'react';
import { Bar } from 'react-chartjs-2';
import { useTranslation } from 'react-i18next';
import { stringToColor } from 'utils/utils';

const Assessment = forwardRef<any, { analytic: Analytic }>(({ analytic }, ref) => {
  const { t } = useTranslation();
  const { bar } = useMyChart();

  const [loading, setLoading] = useState(false);
  const [assessmentData, setAssessmentData] = useState<HowlerFacetSearchResponse>({});

  useEffect(() => {
    if (!analytic) {
      return;
    }

    setLoading(true);

    api.search.facet.hit
      .post({
        fields: ['howler.assessment'],
        query: `howler.analytic:("${analytic.name}")`
      })
      .then(data => setAssessmentData(data['howler.assessment']))
      .finally(() => setLoading(false));
  }, [analytic]);

  if (!loading && assessmentData.length < 1) {
    return (
      <Box sx={{ minHeight: '300px', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Typography
          variant="h4"
          sx={theme => ({
            color: theme.palette.divider
          })}
        >
          {t('no.data')}
        </Typography>
      </Box>
    );
  }

  return analytic && !loading ? (
    <Bar
      ref={ref as any}
      options={bar('route.analytics.assessment.title', '')}
      data={{
        labels: Object.keys(assessmentData),
        datasets: [
          {
            label: '',
            data: Object.values(assessmentData),
            borderColor: Object.keys(assessmentData).map(_analytic => stringToColor(_analytic)),
            backgroundColor: Object.keys(assessmentData).map(_analytic => stringToColor(_analytic))
          }
        ]
      }}
    />
  ) : (
    <Skeleton variant="rounded" height={200} />
  );
});

export default Assessment;
