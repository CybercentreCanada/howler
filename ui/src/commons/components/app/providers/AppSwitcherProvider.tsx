import type { AppSwitcherItem } from 'commons/components/app/AppConfigs';
import { useMemo, useState, type ReactNode } from 'react';

import { AppSwitcherContext } from 'commons/components/app/AppContexts';
import { useAppConfigs } from 'commons/components/app/hooks';

type AppSwitcherProviderProps = {
  children: ReactNode;
};

export default function AppSwitcherProvider({ children }: AppSwitcherProviderProps) {
  const { preferences } = useAppConfigs();
  const [items, setItems] = useState<AppSwitcherItem[]>(preferences.topnav.apps || []);
  const context = useMemo(() => ({ items, empty: !items || items.length === 0, setItems }), [items]);
  return <AppSwitcherContext.Provider value={context}>{children}</AppSwitcherContext.Provider>;
}
