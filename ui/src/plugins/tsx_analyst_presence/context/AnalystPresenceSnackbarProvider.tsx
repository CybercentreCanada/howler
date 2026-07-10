import { useMemo, useState } from 'react';
import { AnalystPresenceSnackbarContext, type AnalystPresenceSnackbarMessage } from './AnalystPresenceSnackbarContext';

export const AnalystPresenceSnackbarProvider = ({ children }: { children: React.ReactNode }) => {
  const [snackbarMessage, setSnackbarMessage] = useState<AnalystPresenceSnackbarMessage | null>(null);

  const contextValue = useMemo(
    () => ({
      snackbarMessage,
      setSnackbarMessage
    }),
    [snackbarMessage]
  );

  return (
    <AnalystPresenceSnackbarContext.Provider value={contextValue}>{children}</AnalystPresenceSnackbarContext.Provider>
  );
};
