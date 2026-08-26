import { sortBy, uniqBy } from 'lodash-es';
import type { FC } from 'react';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import type { Analytic } from 'models/entities/generated/Analytic';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { Hit } from 'models/entities/generated/Hit';

import { useAppPivotGroup } from 'commons/components/app/hooks';
import ResolvePivotUrl from 'components/elements/hit/ResolvePivotUrl';
import pivotForest from 'utils/pivotForest';

interface HitLinksProps {
  hit?: Hit;
  analytic?: Analytic;
  dossiers?: Dossier[];
}

const HitLinks: FC<HitLinksProps> = ({ hit, analytic, dossiers = [] }) => {
  const { i18n } = useTranslation();
  const pivotGroup = useAppPivotGroup();

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

  // Hide the section when the hit has no direct links, no pivot entries in either the grouped or legacy view,
  // and no attached notebooks. This prevents empty link panels from rendering in the hit details UI.
  if (
    useMemo(() => uniqBy(hit?.howler?.links ?? [], 'href').slice(0, 3), [hit?.howler?.links]).length === 0 &&
    !(pivotGroup.enabled ? rootPivots.length > 0 || groups.length > 0 : flatPivots.length > 0) &&
    !((analytic?.notebooks?.length ?? 0) > 0)
  ) {
    return null;
  }
};

export default HitLinks;
