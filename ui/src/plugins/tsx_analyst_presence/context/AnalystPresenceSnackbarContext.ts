import type { AlertProps } from '@mui/material/Alert';
import { createContext } from 'react';

export type AnalystPresenceSnackbarMessage = {
  type: AlertProps['severity'];
  message: string;
};

export type AnalystPresenceSnackbarContextType = {
  snackbarMessage: AnalystPresenceSnackbarMessage | null;
  setSnackbarMessage: (message: AnalystPresenceSnackbarMessage | null) => void;
};

export const AnalystPresenceSnackbarContext = createContext<AnalystPresenceSnackbarContextType | null>(null);
