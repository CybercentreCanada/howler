import { Icon } from '@iconify/react/dist/iconify.js';
import { Skeleton } from '@mui/material';
import Handlebars from 'handlebars';
import { isEmpty } from 'lodash-es';
import type { Hit } from 'models/entities/generated/Hit';
import type { Pivot } from 'models/entities/generated/Pivot';
import { useMemo, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { flattenDeep } from 'utils/utils';
import RelatedLink from './RelatedLink';

const PivotLink: FC<{ pivot: Pivot; hit: Hit; compact?: boolean }> = ({ pivot, hit, compact = false }) => {
  const { i18n } = useTranslation();

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
    return (
      <RelatedLink title={pivot.label[i18n.language]} href={href} compact={compact}>
        <Icon fontSize="1.5rem" icon={pivot.icon} />
      </RelatedLink>
    );
  }

  return <Skeleton variant="rounded" />;
};

export default PivotLink;
