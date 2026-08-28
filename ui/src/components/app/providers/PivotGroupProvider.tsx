import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import { createContext, useContext, useMemo, type FC, type PropsWithChildren } from 'react';
import { StorageKey } from 'utils/constants';

interface PivotGroupContextType {
  enabled: boolean;
  toggle: () => void;
}

const PivotGroupContext = createContext<PivotGroupContextType>(null);

export const usePivotGroup = (): PivotGroupContextType => {
  const context = useContext(PivotGroupContext);

  if (!context) {
    throw new Error('usePivotGroup must be used within PivotGroupProvider');
  }

  return context;
};

const PivotGroupProvider: FC<PropsWithChildren> = ({ children }) => {
  const [enabled, setEnabled] = useMyLocalStorageItem(StorageKey.PIVOT_GROUP, true);
  const context = useMemo(() => ({ enabled, toggle: () => setEnabled(!enabled) }), [enabled, setEnabled]);

  return <PivotGroupContext.Provider value={context}>{children}</PivotGroupContext.Provider>;
};

export default PivotGroupProvider;
