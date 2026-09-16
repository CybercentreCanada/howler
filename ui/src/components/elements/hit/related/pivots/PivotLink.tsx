import { ErrorOutline } from '@mui/icons-material';
import { Box, Tooltip, Typography } from '@mui/material';
import { useHelpers } from 'components/elements/display/handlebars/helpers';
import HowlerCard from 'components/elements/display/HowlerCard';
import PivotTooltip from 'components/elements/hit/PivotTooltip';
import { resolvePivotUrl } from 'components/elements/hit/related/pivots/utils';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { Hit } from 'models/entities/generated/Hit';
import type { Pivot } from 'models/entities/generated/Pivot';
import howlerPluginStore from 'plugins/store';
import React, { useMemo, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { usePluginStore } from 'react-pluggable';
import RelatedLink from '../RelatedLink';

export interface PivotLinkProps {
  pivot: Pivot;
  hit?: Hit;
  compact?: boolean;
  dossier: Dossier;
  variant?: 'card' | 'menu-item';
  onNavigate?: () => void;
}
const PivotLink: FC<PivotLinkProps> = ({ pivot, hit, compact = false, dossier, variant = 'card', onNavigate }) => {
  const { i18n } = useTranslation();

  const helpers = useHelpers({ async: false, components: false });
  const pluginStore = usePluginStore();

  const resolvedUrl = useMemo(
    () =>
      pivot.format === 'link'
        ? resolvePivotUrl(pivot, hit, helpers) || `/dossier/${dossier.dossier_id}`
        : `/dossier/${dossier.dossier_id}`,
    [dossier.dossier_id, helpers, hit, pivot]
  );

  if (pivot.format === 'link') {
    return (
      <RelatedLink
        title={pivot.label?.[i18n.language as 'en' | 'fr'] ?? pivot.value ?? ''}
        href={resolvedUrl}
        icon={pivot.icon}
        target="_blank"
        rel="noopener noreferrer"
        compact={compact}
        dense={variant === 'menu-item'}
        secondary={
          variant === 'menu-item' ? (
            <>
              <Typography variant="caption" display="block" color="text.secondary" noWrap>
                {[dossier.title, dossier.owner].filter(Boolean).join(' • ')}
              </Typography>
              <Typography variant="caption" display="block" color="text.secondary" noWrap sx={{ maxWidth: 260 }}>
                {resolvedUrl}
              </Typography>
            </>
          ) : undefined
        }
        tooltip={variant === 'menu-item' ? undefined : <PivotTooltip dossier={dossier} resolvedUrl={resolvedUrl} />}
        menuItem={variant === 'menu-item'}
        onNavigate={onNavigate}
      />
    );
  }

  const pluginPivot: React.ReactElement | null = howlerPluginStore.pivotFormats.includes(pivot.format ?? '')
    ? pluginStore.executeFunction(`pivot.${pivot.format}`, { pivot, hit, compact, variant, onNavigate })
    : null;

  if (pluginPivot) {
    if (variant === 'menu-item') {
      return pluginPivot;
    }

    return (
      <Tooltip title={<PivotTooltip dossier={dossier} resolvedUrl={resolvedUrl} />}>
        <Box component="span" sx={{ display: 'inline-flex' }}>
          {pluginPivot}
        </Box>
      </Tooltip>
    );
  }

  if (variant === 'menu-item') {
    return (
      <Box
        role="menuitem"
        aria-disabled="true"
        tabIndex={-1}
        sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 1, py: 0.5 }}
      >
        <ErrorOutline color="error" fontSize="small" />
        <Typography noWrap>{`Missing Pivot Implementation ${pivot.format}`}</Typography>
      </Box>
    );
  }

  return (
    <HowlerCard
      sx={[
        theme => ({
          p: 0.75,
          backgroundColor: 'transparent',
          transition: theme.transitions.create(['border-color']),
          '&:hover': { borderColor: 'error.main' }
        }),
        { border: 'thin solid', borderColor: 'transparent' }
      ]}
    >
      <Tooltip
        title={
          <>
            <span>{`Missing Pivot Implementation ${pivot.format}`}</span>
            <code>
              <pre>{JSON.stringify(pivot, null, 4)}</pre>
            </code>
          </>
        }
        slotProps={{
          popper: {
            sx: {
              '& > .MuiTooltip-tooltip': {
                maxWidth: '90vw !important'
              }
            }
          }
        }}
      >
        <ErrorOutline color="error" />
      </Tooltip>
    </HowlerCard>
  );
};

export default PivotLink;
