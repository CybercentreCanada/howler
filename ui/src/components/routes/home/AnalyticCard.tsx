import { CenterFocusWeak, OpenInNew } from '@mui/icons-material';
import { Box, Card, CardContent, IconButton, Skeleton, Stack, Tooltip, Typography } from '@mui/material';
import type { Chart } from 'chart.js';
import { AnalyticContext } from 'components/app/providers/AnalyticProvider';
import FlexOne from 'components/elements/addons/layout/FlexOne';
import type { Analytic } from 'models/entities/generated/Analytic';
import type { FC } from 'react';
import { useContext, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import Assessment from '../analytics/widgets/Assessment';
import Created from '../analytics/widgets/Created';
import Detection from '../analytics/widgets/Detection';
import Escalation from '../analytics/widgets/Escalation';
import Status from '../analytics/widgets/Status';

export interface AnalyticSettings {
  analyticId: string;
  type: 'assessment' | 'created' | 'escalation';
}

const AnalyticCard: FC<AnalyticSettings> = ({ analyticId, type }) => {
  const { t } = useTranslation();
  const [analytic, setAnalytic] = useState<Analytic>(null);
  const { getAnalyticFromId } = useContext(AnalyticContext);

  const chartRef = useRef<Chart>();

  useEffect(() => {
    getAnalyticFromId(analyticId).then(setAnalytic);
  }, [analyticId, getAnalyticFromId]);

  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardContent sx={{ height: '100%' }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="h6">
            {analytic?.name ?? <Skeleton variant="text" height="2em" width="100px" />}
          </Typography>
          <IconButton size="small" component={Link} to={`/analytics/${analytic?.analytic_id}`}>
            <OpenInNew fontSize="small" />
          </IconButton>
          <FlexOne />
          {!['assessment', 'escalation'].includes(type) && (
            <Tooltip title={t('hit.summary.zoom.reset')}>
              <IconButton onClick={() => chartRef.current?.resetZoom()}>
                <CenterFocusWeak />
              </IconButton>
            </Tooltip>
          )}
        </Stack>
        {{
          assessment: () => <Assessment ref={chartRef} analytic={analytic} />,
          created: () => <Created ref={chartRef} analytic={analytic} />,
          status: () => <Status ref={chartRef} analytic={analytic} />,
          detection: () => <Detection ref={chartRef} analytic={analytic} />,
          escalation: () => (
            <Box sx={{ display: 'flex', justifyContent: 'center' }}>
              <Escalation analytic={analytic} maxWidth="80%" />
            </Box>
          )
        }[type]()}
      </CardContent>
    </Card>
  );
};

export default AnalyticCard;
