import { MoreHoriz } from '@mui/icons-material';
import { Breadcrumbs as MuiBreadcrumbs, Tooltip } from '@mui/material';
import { type BreadcrumbItem } from 'commons/components/app/hooks';
import BreadcrumbLastItem from 'commons/components/breadcrumbs/BreadcrumbLastItem';
import BreadcrumbLinkItem from 'commons/components/breadcrumbs/BreadcrumbLinkItem';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

type BreadcrumbListProps = {
  disableStyle?: boolean;
  textOnly?: boolean;
  isStatic?: boolean;
  itemsBefore?: number;
  itemsAfter?: number;
  items: BreadcrumbItem[];
};

const splitItems = (
  items: BreadcrumbItem[],
  itemsBeforeCount: number,
  itemsAfterCount: number,
  expanded: boolean,
  isStatic: boolean
): { before: BreadcrumbItem[]; after: BreadcrumbItem[]; hasEllipsis: boolean } => {
  const _items = items.concat().filter(i => !i.route.exclude);
  const hasEllipsis = _items.length > itemsBeforeCount + itemsAfterCount;
  if (!hasEllipsis || isStatic) {
    return { before: null, after: _items, hasEllipsis: false };
  }
  const before = _items.slice(0, itemsBeforeCount);
  const after = expanded ? _items.slice(itemsBeforeCount) : _items.slice(_items.length - itemsAfterCount);
  return { before, after, hasEllipsis: hasEllipsis || expanded };
};

const BreadcrumbsEllipsis = ({ onClick, expanded }) => {
  const { t } = useTranslation();
  return (
    <Tooltip title={t(expanded ? 'tooltip.breadcrumbs.min' : 'tooltip.breadcrumbs.max')}>
      <MoreHoriz
        fontSize="small"
        sx={{
          verticalAlign: 'bottom',
          marginTop: '5px',
          display: 'inline-flex',
          '&:hover': {
            cursor: 'pointer'
          }
        }}
        onClick={onClick}
      />
    </Tooltip>
  );
};

export default function BreadcrumbList({
  items,
  disableStyle,
  itemsBefore,
  itemsAfter,
  textOnly,
  isStatic
}: BreadcrumbListProps) {
  const [expanded, setExpanded] = useState<boolean>(false);
  const { before, after, hasEllipsis } = splitItems(items, itemsBefore, itemsAfter, expanded, isStatic);
  const last = after.length > 0 ? after.pop() : null;
  return (
    <MuiBreadcrumbs
      aria-label="breadcrumb"
      maxItems={1000}
      style={{
        ...(!disableStyle && {
          color: 'inherit',
          display: 'flex',
          alignItems: 'center',
          flexGrow: 2
        })
      }}
    >
      {before &&
        before.map(item => <BreadcrumbLinkItem key={`bcrumb-${item.route.path}`} item={item} textOnly={textOnly} />)}
      {hasEllipsis && <BreadcrumbsEllipsis expanded={expanded} onClick={() => setExpanded(!expanded)} />}
      {after &&
        after.map(item => <BreadcrumbLinkItem key={`bcrumb-${item.route.path}`} item={item} textOnly={textOnly} />)}
      {last && <BreadcrumbLastItem item={last} textOnly={textOnly} />}
    </MuiBreadcrumbs>
  );
}
