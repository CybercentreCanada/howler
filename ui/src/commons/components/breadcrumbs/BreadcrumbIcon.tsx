import { useTheme } from '@mui/material';
import { type BreadcrumbItem } from 'commons/components/app/hooks/useAppSitemap';

type BreadcrumbIconProps = {
  item: BreadcrumbItem;
};

const BreadcrumbIcon: React.FC<BreadcrumbIconProps> = ({ item }) => {
  const theme = useTheme();
  const {
    route: { icon }
  } = item;
  return icon ? (
    <>
      {icon}
      <span style={{ marginRight: theme.spacing(1) }} />
    </>
  ) : null;
};

export default BreadcrumbIcon;
