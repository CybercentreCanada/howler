import { Link, Tooltip } from '@mui/material';
import { useAppSitemap, type BreadcrumbItem } from 'commons/components/app/hooks';
import BreadcrumbIcon from 'commons/components/breadcrumbs/BreadcrumbIcon';
import { Link as RouterLink } from 'react-router-dom';

type BreadcrumbLinkItemProps = {
  textOnly?: boolean;
  item: BreadcrumbItem;
};

const BreadcrumbLinkItem: React.FC<BreadcrumbLinkItemProps> = ({ item, textOnly }) => {
  const { route, matcher } = item;
  const { getTitle: resolveTitle } = useAppSitemap();
  const url = matcher ? matcher.pathname : route.path;
  return (
    <Link
      component={RouterLink}
      key={`bcrumb-${url}`}
      color="inherit"
      to={url}
      style={{
        display: 'flex',
        alignItems: 'center'
      }}
    >
      {!textOnly && <BreadcrumbIcon item={item} />}
      <Tooltip title={url}>
        <span
          style={{
            maxWidth: route.textWidth || '200px',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap'
          }}
        >
          {resolveTitle(item)}
        </span>
      </Tooltip>
    </Link>
  );
};

export default BreadcrumbLinkItem;
