import { AppBarContext } from 'commons/components/app/AppContexts';
import { useContext } from 'react';

export function useAppBar() {
  return useContext(AppBarContext);
}
