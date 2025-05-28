import { useScrollRestoration } from 'components/hooks/useScrollRestoration';
import type { FC, PropsWithChildren } from 'react';

export const BundleScroller: FC<PropsWithChildren> = ({ children }) => {
  useScrollRestoration('hitscrollbar');

  return <>{children}</>;
};
