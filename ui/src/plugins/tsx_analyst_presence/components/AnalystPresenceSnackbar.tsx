import Alert from '@mui/material/Alert';
import Snackbar from '@mui/material/Snackbar';
import { useAnalystPresenceSnackbar } from '../hooks/useAnalystPresenceSnackbar';

export const AnalystPresenceSnackbar = () => {
  const { snackbarMessage, setSnackbarMessage } = useAnalystPresenceSnackbar();

  return (
    <Snackbar
      open={snackbarMessage !== null}
      autoHideDuration={6000}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      onClose={() => setSnackbarMessage(null)}
    >
      <Alert severity={snackbarMessage?.type} variant="filled" onClose={() => setSnackbarMessage(null)}>
        {snackbarMessage?.message}
      </Alert>
    </Snackbar>
  );
};
