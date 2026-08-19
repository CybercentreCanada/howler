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

interface HitLinksProps {
  hit?: Hit;
  analytic?: Analytic;
  dossiers?: Dossier[];
}

const HitLinks: FC<HitLinksProps> = ({ hit, analytic, dossiers = [] }) => {
  const { i18n } = useTranslation();
  // Tree data structure for pivot

  // {
  //   "root"{
  //     "other parent" {
  //     "other parent"{...}
  //       "pivot":[]
  //     },
  //     "pivot":[]
  //   }
  // }
  type PivotTree = {
    pivot?: Pivot[];
    [key: string]: any;
  };

  const groupPivot: PivotTree = {};

  for (const dossier of dossiers) {
    for (const pivot of dossier.pivots) {
      let current = groupPivot;
      // Doesn't have a group it will not be class
      if (pivot.group === '') {
        if (!('pivot' in current)) {
          current['pivot'] = [];
        }
        current['pivot'].push(pivot);
        continue;
      }
      // Sort it into group
      const group = pivot.group.split('/');
      for (let i = 0; i < group.length; i++) {
        let key = group[i];
        if (!(key in current)) {
          current[key] = {};
        }
        current = current[key];
      }

      if (!('pivot' in current)) {
        current['pivot'] = [];
      }

      current['pivot'].push(pivot);
    }
  }

  const displayLinks = useMemo(() => uniqBy(hit?.howler?.links ?? [], 'href').slice(0, 3), [hit?.howler?.links]);

  const displayPivots = useMemo(() => {
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
