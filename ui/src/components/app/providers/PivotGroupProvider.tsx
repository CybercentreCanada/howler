import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import { createContext, useContext, useMemo, type FC, type PropsWithChildren } from 'react';
import { StorageKey } from 'utils/constants';

// Provides a shared toggle that keeps the pivot-grouping preference persisted in local storage
// and exposes it to any component that needs to enable or disable grouped pivot behavior.

interface PivotGroupContextType {
  enabled: boolean;
  toggle: () => void;
}

const PivotGroupContext = createContext<PivotGroupContextType>(null);

// Returns the current pivot-group state and toggle function for consumers within the provider.
export const usePivotGroup = (): PivotGroupContextType => {
  const context = useContext(PivotGroupContext);

  if (!context) {
    throw new Error('usePivotGroup must be used within PivotGroupProvider');
  }

  return context;
};

// Stores the user's pivot-grouping preference in local storage and makes it available to descendants.
const PivotGroupProvider: FC<PropsWithChildren> = ({ children }) => {
  const [enabled, setEnabled] = useMyLocalStorageItem(StorageKey.PIVOT_GROUP, true);
  const context = useMemo(() => ({ enabled, toggle: () => setEnabled(!enabled) }), [enabled, setEnabled]);

  return <PivotGroupContext.Provider value={context}>{children}</PivotGroupContext.Provider>;
};

export default PivotGroupProvider;
