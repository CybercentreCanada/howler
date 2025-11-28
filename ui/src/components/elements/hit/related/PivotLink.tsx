import { ErrorOutline } from '@mui/icons-material';
import { Card, Tooltip } from '@mui/material';
import Handlebars from 'handlebars';
import { isEmpty } from 'lodash-es';
import type { Hit } from 'models/entities/generated/Hit';
import type { Pivot } from 'models/entities/generated/Pivot';
import React, { useMemo, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { usePluginStore } from 'react-pluggable';
import { flattenDeep } from 'utils/utils';
import RelatedLink from './RelatedLink';

export interface PivotLinkProps {
  pivot: Pivot;
  hit: Hit;
  compact?: boolean;
}

const PivotLink: FC<PivotLinkProps> = ({ pivot, hit, compact = false }) => {
  const { i18n } = useTranslation();

  const pluginStore = usePluginStore();

  const flatHit = useMemo(() => flattenDeep(hit ?? {}), [hit]);

  const href = useMemo(() => {
    if (!pivot || pivot.format !== 'link' || !flatHit || isEmpty(flatHit)) {
      return '';
    }

    const templateObject = Object.fromEntries(
      pivot.mappings.map(mapping => {
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

    return Handlebars.compile(pivot.value)(templateObject);
  }, [flatHit, pivot]);

  if (href) {
    return <RelatedLink title={pivot.label[i18n.language]} href={href} compact={compact} icon={pivot.icon} />;
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
    <Card variant="outlined" sx={{ display: 'flex', alignItems: 'center', px: 1 }}>
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
    </Card>
  );
};

export default PivotLink;
