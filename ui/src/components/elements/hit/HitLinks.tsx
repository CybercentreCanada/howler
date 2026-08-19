import { Grid, gridClasses } from '@mui/material';
import { sortBy, uniqBy } from 'lodash-es';
import type { FC } from 'react';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import type { Analytic } from 'models/entities/generated/Analytic';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { Hit } from 'models/entities/generated/Hit';

import HitNotebooks from 'components/elements/hit/HitNotebooks';
import ResolvePivotUrl from 'components/elements/hit/ResolvePivotUrl';
import PivotLink from 'components/elements/hit/related/PivotLink';
import RelatedLink from 'components/elements/hit/related/RelatedLink';
import type { Pivot } from 'models/entities/generated/Pivot';
import pivotGrouping from '../../../utils/PivotGrouping';

interface HitLinksProps {
  hit?: Hit;
  analytic?: Analytic;
  dossiers?: Dossier[];
}

const HitLinks: FC<HitLinksProps> = ({ hit, analytic, dossiers = [] }) => {
  const { i18n } = useTranslation();

  const displayLinks = useMemo(() => uniqBy(hit?.howler?.links ?? [], 'href').slice(0, 3), [hit?.howler?.links]);
  // TODO AG: use groupedPivot to know which pivot need to be shown or not.
  // For start lets grab the highest pivot of every tree
  // Then we'll figure out if we can use the same as the right click modal to show the rest on a hover of the cheveron
  const displayPivots = useMemo(() => {
    const groupedPivot = pivotGrouping(dossiers);
    const shownPivot: Pivot[] = [];
    // Root search
    for (const key in groupedPivot) {
      if (key === 'pivot') {
        // TODO: Verify how to properly send a list into an other one
        shownPivot.push(groupedPivot[key] as Pivot); // verify later how to properly push an array into an other one
        continue; // we handle that outside
      }
      continue;
    }

    const flattened = dossiers.flatMap(dossier =>
      (dossier.pivots ?? []).map(pivot => {
        const pivotUrl = pivot.format === 'link' ? ResolvePivotUrl(pivot, hit) : undefined;
        return {
          pivot,
          dossier,
          resolvedUrl: pivotUrl || `/dossier/${dossier.dossier_id}`
        };
      })
    );
    return sortBy(flattened, item => item.pivot.label?.[i18n.language]);
  }, [dossiers, i18n.language, hit]);

  const hasNotebooks = (analytic?.notebooks?.length ?? 0) > 0;

  if (displayLinks.length === 0 && displayPivots.length === 0 && !hasNotebooks) {
    return null;
  }

  return (
    <Grid container spacing={1} pr={2} sx={{ [`& .${gridClasses.item}`]: { display: 'flex' } }}>
      {displayLinks
        .filter(link => !!link.href)
        .map(link => {
          const safeTitle = link.title ?? link.href;

          return (
            <Grid item key={link.href}>
              <RelatedLink compact title={safeTitle} href={link.href} target="_blank" rel="noopener noreferrer" />
            </Grid>
          );
        })}

      {displayPivots.map(({ pivot, dossier, resolvedUrl }) => {
        return (
          <Grid item key={`${dossier.dossier_id}-${pivot.value}`}>
            <PivotLink pivot={pivot} hit={hit} dossier={dossier} resolvedUrl={resolvedUrl} compact />
          </Grid>
        );
      })}
      {hasNotebooks && (
        <Grid item>
          <HitNotebooks analytic={analytic} hit={hit} compact />
        </Grid>
      )}
    </Grid>
  );
};

export default HitLinks;
