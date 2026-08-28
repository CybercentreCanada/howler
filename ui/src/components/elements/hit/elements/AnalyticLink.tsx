import { Link as LinkIcon } from '@mui/icons-material';
import { IconButton, Stack, Typography } from '@mui/material';
import useMatchers from 'components/app/hooks/useMatchers';
import type { Hit } from 'models/entities/generated/Hit';
import { useEffect, useState, type FC } from 'react';
import { Link } from 'react-router';

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

    void getMatchingAnalytic(hit).then(analytic => setAnalyticId(analytic?.analytic_id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hit?.howler.analytic]);

  return (
    <Stack direction="row" alignItems="center" spacing={0.5}>
      <IconButton
        size="small"
        component={Link}
        onAuxClick={e => {
          e.stopPropagation();
        }}
        onClick={e => {
          e.stopPropagation();
        }}
        disabled={!analyticId}
        to={`/analytics/${analyticId}`}
        target="_blank"
        rel="noopener noreferrer"
      >
        <LinkIcon fontSize="small" />
      </IconButton>
      <Typography
        variant={compressed ? 'body1' : 'h6'}
        fontWeight={compressed && 'bold'}
        sx={{ alignSelf, '& a': { color: 'text.primary' } }}
      >
        {hit.howler.analytic}
        {hit.howler.detection && ' > '}
        {hit.howler.detection}
      </Typography>
    </Stack>
  );
};

export default AnalyticLink;
