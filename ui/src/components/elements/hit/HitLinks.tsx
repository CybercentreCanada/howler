import { Box, Grid, gridClasses, Link, Tooltip, Typography } from '@mui/material';
import Handlebars from 'handlebars';
import { sortBy, uniqBy } from 'lodash-es';
import type { FC } from 'react';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { flattenDeep } from 'utils/utils';

import HitNotebooks from 'components/elements/hit/HitNotebooks';
import PivotLink from 'components/elements/hit/related/PivotLink';
import RelatedLink from 'components/elements/hit/related/RelatedLink';

import type { Analytic } from 'models/entities/generated/Analytic';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { Hit } from 'models/entities/generated/Hit';

// region: Helper Functions
const resolvePivotUrl = (pivot: NonNullable<Dossier['pivots']>[number], currentHit?: Hit): string => {
  const flatHit = flattenDeep(currentHit ?? {});

  const templateObject = Object.fromEntries(
    (pivot.mappings ?? []).map(mapping => {
      const value =
        mapping.field === 'custom'
          ? mapping.custom_value
          : Array.isArray(flatHit[mapping.field])
            ? flatHit[mapping.field][0]
            : flatHit[mapping.field];

      return [mapping.key, value];
    })
  );

  try {
    return Handlebars.compile(pivot.value)(templateObject);
  } catch {
    return pivot.value;
  }
};

const RelatedLinkTooltip: FC<{ title: string; href: string }> = ({ title, href }) => (
  <Box sx={{ maxWidth: 300 }}>
    <Typography variant="subtitle2">{title}</Typography>
    <Box sx={{ mt: 1, wordBreak: 'break-all' }}>
      <Link href={href} target="_blank" rel="noopener noreferrer" underline="hover">
        {href}
      </Link>
    </Box>
    <Box sx={{ mt: 2 }}>
      <Link href={href} target="_blank" rel="noopener noreferrer" underline="hover">
        {'Open Link'}
      </Link>
    </Box>
  </Box>
);

const PivotTooltip: FC<{ dossier: Dossier; resolvedUrl: string }> = ({ dossier, resolvedUrl }) => {
  const dossierUrl = `/dossiers/${dossier.dossier_id}/edit?tab=leads&query=${encodeURIComponent(dossier.query)}`;

  return (
    <Box sx={{ maxWidth: 300 }}>
      <Typography variant="subtitle2">{dossier.title}</Typography>
      <Typography variant="body2" color="text.secondary">
        {dossier.owner}
      </Typography>
      <Typography variant="body2" sx={{ mt: 2 }}>
        {dossier.leads?.[0]?.content?.slice(0, 120) ?? 'No description'}
      </Typography>
      <Box sx={{ mt: 2, wordBreak: 'break-all' }}>
        <Typography variant="caption" display="block">
          {'URL : '}
        </Typography>
        <Link href={resolvedUrl} target="_blank" rel="noopener noreferrer" underline="hover">
          {resolvedUrl}
        </Link>
      </Box>
      <Box sx={{ mt: 2 }}>
        <Link href={dossierUrl} target="_blank" rel="noopener noreferrer" underline="hover">
          {'Open Dossier'}
        </Link>
      </Box>
    </Box>
  );
};

const NotebookTooltip: FC = () => (
  <Box sx={{ maxWidth: 300 }}>
    <Typography variant="subtitle2">{'Notebook'}</Typography>
    <Typography variant="body2" color="text.secondary">
      {'Opens notebook panel'}
    </Typography>
  </Box>
);
// enregion

//region main object
interface HitLinksProps {
  hit?: Hit;
  analytic?: Analytic;
  dossiers?: Dossier[];
}

const HitLinks: FC<HitLinksProps> = ({ hit, analytic, dossiers = [] }) => {
  const { i18n } = useTranslation();

  // 1. Prepare and memoize unique related links
  const displayLinks = useMemo(() => uniqBy(hit?.howler?.links ?? [], 'href').slice(0, 3), [hit?.howler?.links]);

  // 2. Flatten and sort pivots cleanly away from the rendering chunk
  const displayPivots = useMemo(() => {
    const flattened = dossiers.flatMap(dossier => (dossier.pivots ?? []).map(pivot => ({ pivot, dossier })));
    return sortBy(flattened, item => item.pivot.label?.[i18n.language]);
  }, [dossiers, i18n.language]);

  const hasNotebooks = (analytic?.notebooks?.length ?? 0) > 0;

  // 3. Clean early return means we drop a level of indentation down below
  if (displayLinks.length === 0 && displayPivots.length === 0 && !hasNotebooks) {
    return null;
  }

  return (
    <Grid container spacing={1} pr={2} sx={{ [`& .${gridClasses.item}`]: { display: 'flex' } }}>
      {/* Related Links */}
      {displayLinks.map(link => (
        <Grid item key={link.href}>
          <Tooltip title={<RelatedLinkTooltip title={link.title} href={link.href} />}>
            <span>
              <RelatedLink compact {...link} target="_blank" rel="noopener noreferrer" />
            </span>
          </Tooltip>
        </Grid>
      ))}

      {/* Pivot Links */}
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

      {/* Notebooks */}
      {hasNotebooks && (
        <Grid item>
          <Tooltip title={<NotebookTooltip />}>
            <span>
              <HitNotebooks analytic={analytic} hit={hit} compact />
            </span>
          </Tooltip>
        </Grid>
      )}
    </Grid>
  );
};

// endregion

export default HitLinks;
