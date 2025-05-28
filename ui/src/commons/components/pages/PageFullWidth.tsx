import PageContent from 'commons/components/pages//PageContent';
import { memo } from 'react';

type PageFullWidthProps = {
  children: React.ReactNode;
  height?: number | string;
  margin?: number;
  mb?: number;
  ml?: number;
  mr?: number;
  mt?: number;
};

const PageFullWidth: React.FC<PageFullWidthProps> = ({
  children,
  height,
  margin = null,
  mb = 2,
  ml = 2,
  mr = 2,
  mt = 2
}) => {
  return (
    <PageContent width="100%" height={height} margin={margin} mb={mb} ml={ml} mr={mr} mt={mt}>
      {children}
    </PageContent>
  );
};

export default memo(PageFullWidth);
