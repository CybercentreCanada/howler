import { Icon } from '@iconify/react';
import { ErrorOutline } from '@mui/icons-material';
import { IconButton, Tooltip, Typography } from '@mui/material';
import { useHelpers } from 'components/elements/display/handlebars/helpers';
import HowlerCard from 'components/elements/display/HowlerCard';
import PivotTooltip from 'components/elements/hit/PivotTooltip';
import Handlebars from 'handlebars';
import { isEmpty } from 'lodash-es';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { Hit } from 'models/entities/generated/Hit';
import type { Pivot } from 'models/entities/generated/Pivot';
import React, { useMemo, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { usePluginStore } from 'react-pluggable';
import { Link } from 'react-router-dom';
import { flattenDeep } from 'utils/utils';
import RelatedLink from './RelatedLink';

type HandlebarsInstance = typeof Handlebars;

export interface PivotLinkProps {
  pivot: Pivot;
  hit: Hit;
  compact?: boolean;
  dossier: Dossier;
  resolvedUrl: string;
  // list-item rendering used inside dropdown menus: no card outline, title/owner/dossier settings shown inline
  dense?: boolean;
  // renders just the icon/label content, no card/border - used when a parent element supplies the shared button chrome
  bare?: boolean;
}
const PivotLink: FC<PivotLinkProps> = ({
  pivot,
  hit,
  compact = false,
  dossier,
  resolvedUrl,
  dense = false,
  bare = false
}) => {
  const { i18n, t } = useTranslation();

  const helpers = useHelpers({ async: false, components: false });
  const pluginStore = usePluginStore();

  const handlebars: HandlebarsInstance = useMemo(() => Handlebars.create(), []);

  const flatHit = useMemo(() => flattenDeep(hit ?? {}), [hit]);

  const href = useMemo(() => {
    if (!pivot || pivot.format !== 'link' || !flatHit || isEmpty(flatHit)) {
      return '';
    }

    const templateObject = Object.fromEntries(
      (pivot.mappings ?? []).map(mapping => {
        const result = [mapping.key];

        if (mapping.field === 'custom') {
          result.push(mapping.custom_value);
        } else if (Array.isArray(flatHit[mapping.field])) {
          result.push(flatHit[mapping.field][0]);
        } else {
          result.push(flatHit[mapping.field]);
        }

        return result;
      })
    );

    helpers.forEach(helper => {
      if (handlebars.helpers[helper.keyword]) {
        return;
      }

      handlebars.registerHelper(helper.keyword, (...args: any[]) => {
        // eslint-disable-next-line no-console
        console.debug(`Running helper ${helper.keyword}`);

        return helper.callback(...args);
      });
    });

    try {
      return handlebars.compile(pivot.value)(templateObject);
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error(`Failed to compile pivot template for value "${pivot.value}":`, e);
      return pivot.value;
    }
  }, [flatHit, pivot, handlebars, helpers]);

  if (href) {
    if (dense) {
      const dossierUrl = `/dossiers/${dossier.dossier_id}/edit?tab=leads&query=${encodeURIComponent(dossier.query)}`;

      return (
        <RelatedLink
          title={pivot.label[i18n.language]}
          href={href}
          icon={pivot.icon}
          target="_blank"
          rel="noopener noreferrer"
          dense
          secondary={
            <>
              <Typography variant="caption" display="block" color="text.secondary" noWrap>
                {[dossier.title, dossier.owner].filter(Boolean).join(' • ')}
              </Typography>
              <Typography variant="caption" display="block" color="text.secondary" noWrap sx={{ maxWidth: 260 }}>
                {href}
              </Typography>
            </>
          }
          action={
            <Tooltip title={t('pivot.dossier.open')}>
              <IconButton
                size="small"
                component={Link}
                to={dossierUrl}
                onClick={e => e.stopPropagation()}
                sx={{ flexShrink: 0 }}
              >
                <Icon icon="mdi:folder-open-outline" fontSize="1.1rem" />
              </IconButton>
            </Tooltip>
          }
        />
      );
    }

    return (
      <RelatedLink
        title={pivot.label[i18n.language]}
        href={href}
        compact={compact}
        icon={pivot.icon}
        target="_blank"
        rel="noopener noreferrer"
        tooltip={<PivotTooltip dossier={dossier} resolvedUrl={resolvedUrl} />}
        bare={bare}
      />
    );
  }

  // Hide a relatively useless console error, we'll show a UI component instead
  // eslint-disable-next-line no-console
  const oldError = console.error;

  let pluginPivot: React.ReactElement = null;
  try {
    // eslint-disable-next-line no-console
    console.error = () => {};

    pluginPivot = pluginStore.executeFunction(`pivot.${pivot.format}`, { pivot, hit, compact });
  } finally {
    // eslint-disable-next-line no-console
    console.error = oldError;
  }

  if (pluginPivot) {
    return pluginPivot;
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
