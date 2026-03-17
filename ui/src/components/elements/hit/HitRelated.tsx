import { Divider, Grid } from '@mui/material';
import type { Hit } from 'models/entities/generated/Hit';
import type { FC } from 'react';
import RelatedLink from './related/RelatedLink';

const HitRelated: FC<{ hit: Hit }> = ({ hit }) => {
  if (!hit) {
    return null;
  }

  return (
    <Grid container spacing={1} pr={2}>
      {hit.howler.links.map(l => (
        <Grid key={l.title + l.href} item xs={6} sm={4} md={3}>
          <RelatedLink {...l} />
        </Grid>
      ))}
      {hit.howler.links.length > 0 && hit.howler.related.length > 0 && (
        <Grid item xs={12}>
          <Divider />
        </Grid>
      )}
    </Grid>
  );
};

export default HitRelated;
