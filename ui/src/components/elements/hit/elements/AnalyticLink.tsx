import { Typography } from '@mui/material';
import useMatchers from 'components/app/hooks/useMatchers';
import type { Hit } from 'models/entities/generated/Hit';
import { useEffect, useState, type FC } from 'react';
import { Link } from 'react-router-dom';

const AnalyticLink: FC<{ hit: Hit; lazy?: boolean; compressed?: boolean; alignSelf?: string }> = ({
  hit,
  lazy = false,
  compressed,
  alignSelf = 'start'
}) => {
  const { getMatchingAnalytic } = useMatchers(lazy);

  const [analyticId, setAnalyticId] = useState<string>();
  useEffect(() => {
    if (!hit?.howler.analytic) {
      return;
    }

    getMatchingAnalytic(hit).then(analytic => setAnalyticId(analytic?.analytic_id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hit?.howler.analytic]);

  return (
    <Typography
      variant={compressed ? 'body1' : 'h6'}
      fontWeight={compressed && 'bold'}
      sx={{ alignSelf, '& a': { color: 'text.primary' } }}
    >
      {analyticId ? (
        <Link
          to={`/analytics/${analyticId}`}
          onAuxClick={e => {
            e.stopPropagation();
          }}
          onClick={e => {
            e.stopPropagation();
          }}
        >
          {hit.howler.analytic}
        </Link>
      ) : (
        hit.howler.analytic
      )}
      {hit.howler.detection && ': '}
      {hit.howler.detection}
    </Typography>
  );
};

export default AnalyticLink;
