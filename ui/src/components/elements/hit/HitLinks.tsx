import { Grid, gridClasses, Tooltip } from '@mui/material';
import { sortBy, uniqBy } from 'lodash-es';
import type { FC } from 'react';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import type { Analytic } from 'models/entities/generated/Analytic';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { Hit } from 'models/entities/generated/Hit';

import HitNotebooks from 'components/elements/hit/HitNotebooks';
import PivotTooltip from 'components/elements/hit/PivotTooltip';
import RelatedLinkTooltip from 'components/elements/hit/RelatedLinkTooltip';
import ResolvePivotUrl from 'components/elements/hit/ResolvePivotUrl';
import PivotLink from 'components/elements/hit/related/PivotLink';
import RelatedLink from 'components/elements/hit/related/RelatedLink';

interface HitLinksProps {
  hit?: Hit;
  analytic?: Analytic;
  dossiers?: Dossier[];
}

const HitLinks: FC<HitLinksProps> = ({ hit, analytic, dossiers = [] }) => {
  const { i18n } = useTranslation();

  const displayLinks = useMemo(() => uniqBy(hit?.howler?.links ?? [], 'href').slice(0, 3), [hit?.howler?.links]);

  const displayPivots = useMemo(() => {
    const flattened = dossiers.flatMap(dossier => (dossier.pivots ?? []).map(pivot => ({ pivot, dossier })));
    return sortBy(flattened, item => item.pivot.label?.[i18n.language]);
  }, [dossiers, i18n.language]);

  const hasNotebooks = (analytic?.notebooks?.length ?? 0) > 0;

  if (displayLinks.length === 0 && displayPivots.length === 0 && !hasNotebooks) {
    return null;
  }

  return (
    <Grid container spacing={1} pr={2} sx={{ [`& .${gridClasses.item}`]: { display: 'flex' } }}>
      {displayLinks
        .filter(link => !!link.href) // ← ensure href exists
        .map(link => {
          const safeTitle = link.title ?? link.href; // ← fallback title

          return (
            <Grid item key={link.href}>
              <Tooltip title={<RelatedLinkTooltip title={safeTitle} href={link.href} />}>
                <span>
                  <RelatedLink compact title={safeTitle} href={link.href} target="_blank" rel="noopener noreferrer" />
                </span>
              </Tooltip>
            </Grid>
          );
        })}

      {displayPivots.map(({ pivot, dossier }) => {
        const resolvedUrl = resolvePivotUrl(pivot, hit);
        return (
          <Grid item key={`${dossier.dossier_id}-${pivot.value}`}>
            <Tooltip title={<PivotTooltip dossier={dossier} resolvedUrl={resolvedUrl} />}>
              <span>
                <PivotLink pivot={pivot} hit={hit} compact />
              </span>
            </Tooltip>
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
