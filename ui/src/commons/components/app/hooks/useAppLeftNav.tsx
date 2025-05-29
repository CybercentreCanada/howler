import { AppLeftNavContext } from 'commons/components/app/AppContexts';
import { useContext } from 'react';

export function useAppLeftNav() {
  return useContext(AppLeftNavContext);
}
