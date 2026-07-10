import { useContext } from 'react';
import { AnalystPresenceSnackbarContext } from '../context/AnalystPresenceSnackbarContext';

export const useAnalystPresenceSnackbar = () => {
  const context = useContext(AnalystPresenceSnackbarContext);

  if (!context) {
    throw new Error('useAnalystPresenceSnackbar must be used within an AnalystPresenceSnackbarProvider');
  }

  return context;
};
