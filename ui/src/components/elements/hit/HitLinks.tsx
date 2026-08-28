import { Grid, gridClasses } from '@mui/material';
import { sortBy, uniqBy } from 'lodash-es';
import type { FC } from 'react';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import type { Analytic } from 'models/entities/generated/Analytic';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { Hit } from 'models/entities/generated/Hit';

import { usePivotGroup } from 'components/app/providers/PivotGroupProvider';
import HitNotebooks from 'components/elements/hit/HitNotebooks';
import ResolvePivotUrl from 'components/elements/hit/ResolvePivotUrl';
import PivotFolderMenu from 'components/elements/hit/related/PivotFolderMenu';
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
  const pivotGroup = usePivotGroup();

  const displayLinks = useMemo(() => uniqBy(hit?.howler?.links ?? [], 'href').slice(0, 3), [hit?.howler?.links]);

  // grouped: organize pivots into a forest of groups, each with a single root button
  const forest = useMemo(
    () => (pivotGroup.enabled ? pivotForest(dossiers, i18n.language) : []),
    [pivotGroup.enabled, dossiers, i18n.language]
  );
  const rootPivots = useMemo(() => forest.find(node => node.path === '')?.pivots ?? [], [forest]);
  // each distinct top-level group is its own tree, represented by a single root button (its own top node)
  const groups = useMemo(() => forest.filter(node => node.path !== ''), [forest]);

  // ungrouped (legacy): a flat, alphabetically sorted list of every pivot, exactly as it was before grouping
  const flatPivots = useMemo(() => {
    if (pivotGroup.enabled) {
      return [];
    }

    return sortBy(
      dossiers.flatMap(dossier =>
        (dossier.pivots ?? []).map(pivot => {
          const pivotUrl = pivot.format === 'link' ? ResolvePivotUrl(pivot, hit) : undefined;
          return {
            pivot,
            dossier,
            resolvedUrl: pivotUrl || `/dossier/${dossier.dossier_id}`
          };
        })
      ),
      item => item.pivot.label?.[i18n.language]
    );
  }, [pivotGroup.enabled, dossiers, i18n.language, hit]);

  const hasNotebooks = (analytic?.notebooks?.length ?? 0) > 0;

  if (
    displayLinks.length === 0 &&
    !(pivotGroup.enabled ? rootPivots.length > 0 || groups.length > 0 : flatPivots.length > 0) &&
    !hasNotebooks
  ) {
    return null;
  }

  return (
    <Grid container spacing={1} pr={2} sx={{ [`& .${gridClasses.root}`]: { display: 'flex' } }}>
      {displayLinks
        .filter(link => !!link.href)
        .map(link => {
          const safeTitle = link.title ?? link.href;

          return (
            <Grid key={link.href}>
              <RelatedLink compact title={safeTitle} href={link.href} target="_blank" rel="noopener noreferrer" />
            </Grid>
          );
        })}

      {!pivotGroup.enabled &&
        flatPivots.map(({ pivot, dossier, resolvedUrl }) => (
          <Grid key={`${dossier.dossier_id}-${pivot.value}`}>
            <PivotLink pivot={pivot} hit={hit} dossier={dossier} resolvedUrl={resolvedUrl} compact />
          </Grid>
        ))}

      {pivotGroup.enabled &&
        rootPivots.map(({ pivot, dossier }) => {
          const pivotUrl = pivot.format === 'link' ? ResolvePivotUrl(pivot, hit) : undefined;
          const resolvedUrl = pivotUrl || `/dossier/${dossier.dossier_id}`;

          return (
            <Grid key={`${dossier.dossier_id}-${pivot.value}`}>
              <PivotLink pivot={pivot} hit={hit} dossier={dossier} resolvedUrl={resolvedUrl} compact />
            </Grid>
          );
        })}

      {pivotGroup.enabled &&
        groups.map(node => (
          <Grid key={node.path}>
            <PivotFolderMenu node={node} hit={hit} />
          </Grid>
        ))}

      {hasNotebooks && (
        <Grid>
          <HitNotebooks analytic={analytic} hit={hit} compact />
        </Grid>
      )}
    </Grid>
  );
};

export default HitLinks;
