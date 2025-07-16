import { InsertLink } from '@mui/icons-material';
import { Box, IconButton, Skeleton } from '@mui/material';
import useMatchers from 'components/app/hooks/useMatchers';
import ErrorBoundary from 'components/routes/ErrorBoundary';
import type { Hit } from 'models/entities/generated/Hit';
import type { Overview } from 'models/entities/generated/Overview';
import type { FC } from 'react';
import { memo, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import HandlebarsMarkdown from '../display/HandlebarsMarkdown';

const HitOverview: FC<{ content?: string; hit: Hit }> = ({ content, hit }) => {
  const { getMatchingOverview } = useMatchers();

  const [matchingOverview, setMatchingOverview] = useState<Overview>(null);

  useEffect(() => {
    getMatchingOverview(hit).then(setMatchingOverview);
  }, [getMatchingOverview, hit]);

  const link = useMemo(
    () =>
      matchingOverview
        ? `/overviews/view?analytic=${encodeURIComponent(matchingOverview.analytic)}${matchingOverview.detection && '&detection=' + encodeURIComponent(matchingOverview.detection)}`
        : hit
          ? `/overviews/view?analytic=${encodeURIComponent(hit?.howler.analytic)}${hit?.howler.detection && '&detection=' + encodeURIComponent(hit?.howler.detection)}`
          : null,
    [hit, matchingOverview]
  );

  return (
    <Box sx={{ position: 'relative', height: '100%', overflow: 'auto' }}>
      {link && (
        <IconButton
          component={Link}
          to={link}
          sx={theme => ({ position: 'absolute', right: theme.spacing(1), top: theme.spacing(1) })}
        >
          <InsertLink />
        </IconButton>
      )}
      {matchingOverview || content ? (
        <ErrorBoundary>
          <HandlebarsMarkdown md={content ?? matchingOverview.content} object={hit} disableLinks />
        </ErrorBoundary>
      ) : (
        <Skeleton variant="rounded" height="40vh" />
      )}
    </Box>
  );
};

export default memo(HitOverview);
