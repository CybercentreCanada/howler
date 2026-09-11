import { Grid, gridClasses } from '@mui/material';
import { sortBy, uniqBy } from 'lodash-es';
import type { FC } from 'react';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import type { Analytic } from 'models/entities/generated/Analytic';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { Hit } from 'models/entities/generated/Hit';

import HitNotebooks from 'components/elements/hit/HitNotebooks';
import PivotFolderMenu from 'components/elements/hit/related/PivotFolderMenu';
import PivotLink from 'components/elements/hit/related/PivotLink';
import RelatedLink from 'components/elements/hit/related/RelatedLink';
import resolvePivotUrl from 'components/elements/hit/ResolvePivotUrl';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import { StorageKey } from 'utils/constants';
import pivotForest, { getDossierPivotKey } from 'utils/pivotForest';

interface HitLinksProps {
  hit?: Hit;
  analytic?: Analytic;
  dossiers?: Dossier[];
}

const HitLinks: FC<HitLinksProps> = ({ hit, analytic, dossiers = [] }) => {
  const { i18n } = useTranslation();
  const [pivotGroupEnabled] = useMyLocalStorageItem(StorageKey.PIVOT_GROUP, true);

  const displayLinks = useMemo(() => uniqBy(hit?.howler?.links ?? [], 'href').slice(0, 3), [hit?.howler?.links]);

  // grouped: organize pivots into a forest of groups, each with a single root button
  const forest = useMemo(
    () => (pivotGroupEnabled ? pivotForest(dossiers, i18n.language) : []),
    [pivotGroupEnabled, dossiers, i18n.language]
  );
  const rootPivots = useMemo(() => forest.find(node => node.path === '')?.pivots ?? [], [forest]);
  // each distinct top-level group is its own tree, represented by a single root button (its own top node)
  const groups = useMemo(() => forest.filter(node => node.path !== ''), [forest]);

  // ungrouped (legacy): a flat, alphabetically sorted list of every pivot, exactly as it was before grouping
  const flatPivots = useMemo(() => {
    if (pivotGroupEnabled) {
      return [];
    }

    return sortBy(
      dossiers.flatMap(dossier =>
        (dossier.pivots ?? []).map(pivot => {
          const pivotUrl = pivot.format === 'link' ? resolvePivotUrl(pivot, hit) : undefined;
          return {
            pivot,
            dossier,
            resolvedUrl: pivotUrl || `/dossier/${dossier.dossier_id}`
          };
        })
      ),
      item => item.pivot.label?.[i18n.language as 'en' | 'fr']
    );
  }, [pivotGroupEnabled, dossiers, i18n.language, hit]);

  const hasNotebooks = (analytic?.notebooks?.length ?? 0) > 0;

  if (
    displayLinks.length === 0 &&
    !(pivotGroupEnabled ? rootPivots.length > 0 || groups.length > 0 : flatPivots.length > 0) &&
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

      {!pivotGroupEnabled &&
        flatPivots.map(({ pivot, dossier, resolvedUrl }) => (
          <Grid key={getDossierPivotKey({ pivot, dossier })}>
            <PivotLink pivot={pivot} hit={hit} dossier={dossier} resolvedUrl={resolvedUrl} compact />
          </Grid>
        ))}

      {pivotGroupEnabled &&
        rootPivots.map(({ pivot, dossier }) => {
          const pivotUrl = pivot.format === 'link' ? resolvePivotUrl(pivot, hit) : undefined;
          const resolvedUrl = pivotUrl || `/dossier/${dossier.dossier_id}`;

          return (
            <Grid key={getDossierPivotKey({ pivot, dossier })}>
              <PivotLink pivot={pivot} hit={hit} dossier={dossier} resolvedUrl={resolvedUrl} compact />
            </Grid>
          );
        })}

      {pivotGroupEnabled &&
        groups.map(node => (
          <Grid key={node.path}>
            <PivotFolderMenu node={node} hit={hit} />
          </Grid>
        ))}

      {hasNotebooks && (
        <Grid>
          <HitNotebooks analytic={analytic!} hit={hit!} compact />
        </Grid>
      )}
    </Grid>
  );
};

export default HitLinks;
