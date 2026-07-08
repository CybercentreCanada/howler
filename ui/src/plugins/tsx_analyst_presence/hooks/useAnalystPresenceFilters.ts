import { useContext } from 'react';
import { AnalystPresenceFiltersContext } from '../context/AnalystPresenceFiltersContext';

export const useAnalystPresenceFilters = () => {
  const context = useContext(AnalystPresenceFiltersContext);

  if (!context) {
    throw new Error('useAnalystPresenceFilters must be used within an AnalystPresenceFiltersProvider');
  }

  return context;
};
