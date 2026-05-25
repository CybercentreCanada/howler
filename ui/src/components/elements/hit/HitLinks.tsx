import { Grid, gridClasses } from '@mui/material';
import HitNotebooks from 'components/elements/hit/HitNotebooks';
import PivotLink from 'components/elements/hit/related/PivotLink';
import RelatedLink from 'components/elements/hit/related/RelatedLink';
import { sortBy, uniqBy } from 'lodash-es';
import type { Analytic } from 'models/entities/generated/Analytic';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { Hit } from 'models/entities/generated/Hit';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

const HitLinks: FC<{ hit?: Hit; analytic?: Analytic; dossiers: Dossier[] }> = ({ hit, analytic, dossiers = [] }) => {
  const { i18n } = useTranslation();

  return (
    (hit?.howler?.links?.length > 0 ||
      analytic?.notebooks?.length > 0 ||
      dossiers.filter(_dossier => _dossier.pivots?.length > 0).length > 0) && (
      <Grid container spacing={1} pr={2} sx={{ [`& .${gridClasses.item}`]: { display: 'flex' } }}>
        {hit?.howler?.links?.length > 0 &&
          uniqBy(hit.howler.links, 'href')
            .slice(0, 3)
            .map(l => (
              <Grid item key={l.href}>
                <RelatedLink compact {...l} target="_blank" rel="noopener noreferrer" />
              </Grid>
            ))}
        {sortBy(
          dossiers.flatMap(_dossier => _dossier.pivots ?? []),
          `label.${i18n.language}`
        ).map((_pivot, index) => (
          // eslint-disable-next-line react/no-array-index-key
          <Grid item key={_pivot.value + index}>
            <PivotLink pivot={_pivot} hit={hit} compact />
          </Grid>
        ))}
        {analytic?.notebooks?.length > 0 && (
          <Grid item>
            <HitNotebooks analytic={analytic} hit={hit} compact />
          </Grid>
        )}
      </Grid>
    )
  );
};

export default HitLinks;
