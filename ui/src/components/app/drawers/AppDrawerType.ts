import type { ReactNode } from 'react';

export type AppDrawerProps = {
  titleKey: string;
  children: ReactNode;
  onClosed?: () => void;
};
