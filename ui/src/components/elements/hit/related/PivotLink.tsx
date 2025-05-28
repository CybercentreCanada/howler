import { Icon } from '@iconify/react/dist/iconify.js';
import { Skeleton } from '@mui/material';
import Handlebars from 'handlebars';
import { get } from 'lodash-es';
import type { Hit } from 'models/entities/generated/Hit';
import type { Pivot } from 'models/entities/generated/Pivot';
import { useMemo, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import RelatedLink from './RelatedLink';

const PivotLink: FC<{ pivot: Pivot; hit: Hit; compact?: boolean }> = ({ pivot, hit, compact = false }) => {
  const { i18n } = useTranslation();

  const href = useMemo(() => {
    if (!pivot || pivot.format !== 'link' || !hit) {
      return '';
    }

    return Handlebars.compile(pivot.value)(
      Object.fromEntries(
        pivot.mappings.map(mapping => [
          mapping.key,
          mapping.field !== 'custom' ? get(hit, mapping.field) : mapping.custom_value
        ])
      )
    );
  }, [hit, pivot]);

  if (href) {
    return (
      <RelatedLink title={pivot.label[i18n.language]} href={href} compact={compact}>
        <Icon fontSize="1.5rem" icon={pivot.icon} />
      </RelatedLink>
    );
  }

  return <Skeleton variant="rounded" />;
};

export default PivotLink;
