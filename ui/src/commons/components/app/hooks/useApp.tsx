import { AppContext } from 'commons/components/app/AppContexts';
import { useContext } from 'react';

export function useApp() {
  return useContext(AppContext);
}
