import { Grid } from '@mui/material';
import type { Hit } from 'models/entities/generated/Hit';
import type { FC } from 'react';
import RelatedLink from './related/RelatedLink';

const HitRelated: FC<{ hit: Hit }> = ({ hit }) => {
  return (
    <Grid container spacing={1} pr={2}>
      {hit?.howler.links?.map(l => (
        <Grid key={l.title + l.href} item xs={6} sm={4} md={3}>
          <RelatedLink {...l} />
        </Grid>
      ))}
    </Grid>
  );
};

export default HitRelated;
