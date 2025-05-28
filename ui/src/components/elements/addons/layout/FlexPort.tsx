import usePageProps from 'commons/components/pages/hooks/usePageProps';
import { memo } from 'react';

type FlexPortProps = {
  margin?: number;
  mt?: number;
  mr?: number;
  mb?: number;
  ml?: number;
  disableOverflow?: boolean;
  id?: string;
  children: React.ReactNode;
};

const FlexPort = ({ children, disableOverflow = false, id = '', ...props }: FlexPortProps) => {
  const pageProps = usePageProps({ props, defaultOverrides: { height: '100%', mb: 0, ml: 0, mr: 0, mt: 0 } });
  return (
    <div
      className={pageProps.className}
      style={{
        position: 'relative',
        flex: 1,
        marginBottom: pageProps.style.marginBottom,
        marginLeft: pageProps.style.marginLeft,
        marginRight: pageProps.style.marginRight,
        marginTop: pageProps.style.marginTop
      }}
    >
      <div
        style={{ position: 'absolute', top: 0, right: 0, bottom: 0, left: 0, overflow: !disableOverflow && 'auto' }}
        id={id}
      >
        {children}
      </div>
    </div>
  );
};

export default memo(FlexPort);
