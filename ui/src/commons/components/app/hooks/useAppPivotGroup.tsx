import { AppPivotGroupContext } from 'commons/components/app/AppContexts';
import { useContext } from 'react';

export function useAppPivotGroup() {
  return useContext(AppPivotGroupContext);
}
