import { AppSwitcherContext } from 'commons/components/app/AppContexts';
import { useContext } from 'react';

export function useAppSwitcher() {
  return useContext(AppSwitcherContext);
}
