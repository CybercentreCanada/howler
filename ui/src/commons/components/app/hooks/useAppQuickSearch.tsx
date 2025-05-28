import { AppQuickSearchContext } from 'commons/components/app/AppContexts';
import { useContext } from 'react';

export function useAppQuickSearch() {
  return useContext(AppQuickSearchContext);
}
