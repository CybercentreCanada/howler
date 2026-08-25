import { AppStorageKeys } from 'commons/components/app/AppConstants';
import { AppPivotGroupContext } from 'commons/components/app/AppContexts';
import { useAppConfigs } from 'commons/components/app/hooks';
import useLocalStorageItem from 'commons/components/utils/hooks/useLocalStorageItem';
import { useMemo, type ReactElement } from 'react';

const { LS_KEY_PIVOT_GROUP } = AppStorageKeys;

type AppPivotGroupProviderProps = {
  children: ReactElement | ReactElement[];
};

export default function AppPivotGroupProvider({ children }: AppPivotGroupProviderProps) {
  const { preferences } = useAppConfigs();
  const [enabled, setEnabled] = useLocalStorageItem(LS_KEY_PIVOT_GROUP, preferences.defaultPivotGroup);
  const context = useMemo(
    () => ({
      enabled: preferences.allowPivotGroupSelection ? enabled : preferences.defaultPivotGroup,
      setEnabled,
      toggle: () => setEnabled(!enabled)
    }),
    [preferences.allowPivotGroupSelection, preferences.defaultPivotGroup, enabled, setEnabled]
  );
  return <AppPivotGroupContext.Provider value={context}>{children}</AppPivotGroupContext.Provider>;
}
