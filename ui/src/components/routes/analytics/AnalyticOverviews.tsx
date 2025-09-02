import { Article } from '@mui/icons-material';
import { Box, Fab, Skeleton, Stack, Typography, useMediaQuery } from '@mui/material';
import 'chartjs-adapter-dayjs-4';
import AppListEmpty from 'commons/components/display/AppListEmpty';
import { OverviewContext } from 'components/app/providers/OverviewProvider';
import type { Analytic } from 'models/entities/generated/Analytic';
import { useContext, useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import OverviewCard from '../overviews/OverviewCard';

const AnalyticOverviews: FC<{ analytic: Analytic }> = ({ analytic }) => {
  const { t } = useTranslation();
  const isNarrow = useMediaQuery('(max-width: 1800px)');

  const { getOverviews, overviews } = useContext(OverviewContext);
  const matchingOverviews = useMemo(
    () => overviews.filter(_overview => _overview.analytic === analytic?.name),
    [analytic?.name, overviews]
  );

  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    getOverviews().finally(() => setLoading(false));
  }, [getOverviews]);

  if (!analytic) {
    return <Skeleton variant="rounded" width="100%" sx={{ minHeight: '300px', mt: 2 }} />;
  }

  return (
    <Stack spacing={1} position="relative">
      <Fab
        component={Link}
        to={`/overviews/view?analytic=${analytic.name}`}
        variant="extended"
        size="large"
        color="primary"
        sx={theme => ({
          textTransform: 'none',
          position: isNarrow ? 'fixed' : 'absolute',
          right: isNarrow ? theme.spacing(2) : `calc(100% + ${theme.spacing(5)})`,
          whiteSpace: 'nowrap',
          ...(isNarrow ? { bottom: theme.spacing(1) } : { top: theme.spacing(2) })
        })}
      >
        <Article sx={{ mr: 1 }} />
        <Typography>{t('route.overviews.create')}</Typography>
      </Fab>
      {loading && <Skeleton width="100%" height="175px" />}
      {!loading && matchingOverviews.length < 1 && <AppListEmpty />}
      {matchingOverviews.map(overview => (
        <Box
          component={Link}
          to={`/overviews/view?analytic=${overview.analytic}${overview.detection ? '&template=' + overview.detection : ''}`}
          key={overview.overview_id}
          sx={theme => ({
            textDecoration: 'none',
            '& > .MuiCard-root': {
              cursor: 'pointer',
              transition: theme.transitions.create('border-color'),
              '&:hover': { borderColor: 'primary.main' }
            }
          })}
        >
          <OverviewCard overview={overview} />
        </Box>
      ))}
    </Stack>
  );
};

export default AnalyticOverviews;
