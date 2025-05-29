import { AppLayoutContext } from 'commons/components/app/AppContexts';
import { useContext } from 'react';

export function useAppLayout() {
  return useContext(AppLayoutContext);
}
