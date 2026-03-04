import { Grid } from '@mui/material';
import HitNotebooks from 'components/elements/hit/HitNotebooks';
import PivotLink from 'components/elements/hit/related/PivotLink';
import RelatedLink from 'components/elements/hit/related/RelatedLink';
import { uniqBy } from 'lodash-es';
import type { Analytic } from 'models/entities/generated/Analytic';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { Hit } from 'models/entities/generated/Hit';
import type { FC } from 'react';

const HitLinks: FC<{ hit?: Hit; analytic?: Analytic; dossiers: Dossier[] }> = ({ hit, analytic, dossiers = [] }) => {
  return (
    (hit?.howler?.links?.length > 0 ||
      analytic?.notebooks?.length > 0 ||
      dossiers.filter(_dossier => _dossier.pivots?.length > 0).length > 0) && (
      <Grid container spacing={1} pr={2}>
        {hit?.howler?.links?.length > 0 &&
          uniqBy(hit.howler.links, 'href')
            .slice(0, 3)
            .map(l => (
              <Grid item key={l.href}>
                <RelatedLink compact {...l} />
              </Grid>
            ))}
        {dossiers.flatMap(_dossier =>
          (_dossier.pivots ?? []).map((_pivot, index) => (
            // eslint-disable-next-line react/no-array-index-key
            <Grid item key={_dossier.dossier_id + index}>
              <PivotLink pivot={_pivot} hit={hit} compact />
            </Grid>
          ))
        )}
        {analytic?.notebooks?.length > 0 && (
          <Grid item>
            <HitNotebooks analytic={analytic} hit={hit} />
          </Grid>
        )}
      </Grid>
    )
  );
};

export default HitLinks;
