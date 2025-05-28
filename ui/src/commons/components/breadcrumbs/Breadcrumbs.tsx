import { useMediaQuery, useTheme } from '@mui/material';
import { useAppBreadcrumbs, useAppConfigs, useAppSitemap, type BreadcrumbItem } from 'commons/components/app/hooks';
import BreadcrumbList from 'commons/components/breadcrumbs/BreadcrumbList';
import { memo, useMemo } from 'react';

const Breadcrumbs = ({ disableStyle = false }) => {
  const theme = useTheme();
  const isMedium = useMediaQuery(theme.breakpoints.up('md'));
  const configs = useAppConfigs();
  const breadcrumbs = useAppBreadcrumbs();
  const sitemap = useAppSitemap();
  const current = breadcrumbs.last();
  const isStatic = !!current.route.breadcrumbs;
  const isExpanded = isMedium;

  const items = useMemo(() => {
    let _items: BreadcrumbItem[] = null;
    if (sitemap.is404(current)) {
      _items = [current];
    } else if (isStatic) {
      const staticBreadcrumbs = current.route.breadcrumbs.map(path => sitemap.getRoute(path));
      _items = [...staticBreadcrumbs, current];
    } else {
      _items = breadcrumbs.items;
    }
    return _items;
  }, [current, isStatic, breadcrumbs, sitemap]);

  return (
    <BreadcrumbList
      items={items}
      disableStyle={disableStyle}
      isStatic={isStatic}
      itemsBefore={isExpanded ? configs.sitemap.itemsBefore : 0}
      itemsAfter={isExpanded ? configs.sitemap.itemsAfter : 1}
    />
  );
};

export default memo(Breadcrumbs);
