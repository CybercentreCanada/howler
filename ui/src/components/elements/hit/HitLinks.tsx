import { Grid, gridClasses } from '@mui/material';
import { uniqBy } from 'lodash-es';
import type { FC } from 'react';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import type { Analytic } from 'models/entities/generated/Analytic';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { Hit } from 'models/entities/generated/Hit';

import HitNotebooks from 'components/elements/hit/HitNotebooks';
import ResolvePivotUrl from 'components/elements/hit/ResolvePivotUrl';
import PivotFolderTrigger from 'components/elements/hit/related/PivotFolderMenu';
import PivotLink from 'components/elements/hit/related/PivotLink';
import RelatedLink from 'components/elements/hit/related/RelatedLink';
import pivotForest from 'utils/pivotForest';

interface HitLinksProps {
  hit?: Hit;
  analytic?: Analytic;
  dossiers?: Dossier[];
}

const HitLinks: FC<HitLinksProps> = ({ hit, analytic, dossiers = [] }) => {
  const { i18n } = useTranslation();

  const displayLinks = useMemo(() => uniqBy(hit?.howler?.links ?? [], 'href').slice(0, 3), [hit?.howler?.links]);

  const forest = useMemo(() => pivotForest(dossiers, i18n.language), [dossiers, i18n.language]);
  const rootPivots = useMemo(() => forest.find(node => node.path === '')?.pivots ?? [], [forest]);
  // each distinct top-level group is its own tree, represented by a single root button (its own top node)
  const groups = useMemo(() => forest.filter(node => node.path !== ''), [forest]);

  const hasNotebooks = (analytic?.notebooks?.length ?? 0) > 0;

  if (displayLinks.length === 0 && rootPivots.length === 0 && groups.length === 0 && !hasNotebooks) {
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

      {rootPivots.map(({ pivot, dossier }) => {
        const pivotUrl = pivot.format === 'link' ? ResolvePivotUrl(pivot, hit) : undefined;
        const resolvedUrl = pivotUrl || `/dossier/${dossier.dossier_id}`;

        return (
          <Grid item key={`${dossier.dossier_id}-${pivot.value}`}>
            <PivotLink pivot={pivot} hit={hit} dossier={dossier} resolvedUrl={resolvedUrl} compact />
          </Grid>
        );
      })}

      {groups.map(node => (
        <Grid item key={node.path}>
          <PivotFolderTrigger node={node} hit={hit} />
        </Grid>
      ))}

      {hasNotebooks && (
        <Grid item>
          <HitNotebooks analytic={analytic} hit={hit} compact />
        </Grid>
      )}
    </Grid>
  );
};

export default HitLinks;
