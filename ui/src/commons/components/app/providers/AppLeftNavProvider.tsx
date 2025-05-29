import { type AppLeftNavElement } from 'commons/components/app/AppConfigs';
import { AppStorageKeys } from 'commons/components/app/AppConstants';
import { AppLeftNavContext } from 'commons/components/app/AppContexts';
import { useAppConfigs } from 'commons/components/app/hooks';
import useLocalStorageItem from 'commons/components/utils/hooks/useLocalStorageItem';
import { useCallback, useMemo, useState, type ReactNode } from 'react';

const { LS_KEY_LEFTNAV_OPEN } = AppStorageKeys;

type LeftNavProviderProps = {
  children: ReactNode;
};

export default function AppLeftNavProvider({ children }: LeftNavProviderProps) {
  const { preferences } = useAppConfigs();
  const [open, setOpen] = useLocalStorageItem(LS_KEY_LEFTNAV_OPEN, preferences.defaultDrawerOpen);
  const [elements, setElements] = useState<AppLeftNavElement[]>();
  const toggle = useCallback(() => setOpen(!open), [open, setOpen]);
  const context = useMemo(
    () => ({
      open,
      elements: elements || preferences.leftnav.elements,
      setOpen,
      setElements,
      toggle
    }),
    [open, elements, preferences.leftnav.elements, setOpen, toggle]
  );
  return <AppLeftNavContext.Provider value={context}>{children}</AppLeftNavContext.Provider>;
}
