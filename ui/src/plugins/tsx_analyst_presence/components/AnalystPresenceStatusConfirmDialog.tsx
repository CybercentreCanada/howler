import { Button, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle } from '@mui/material';
import { useTranslation } from 'react-i18next';

type AnalystPresenceStatusConfirmDialogProps = {
  open: boolean;
  username: string;
  status: string | null;
  onConfirm: () => void;
  onCancel: () => void;
};

export const AnalystPresenceStatusConfirmDialog = ({
  open,
  username,
  status,
  onConfirm,
  onCancel
}: AnalystPresenceStatusConfirmDialogProps) => {
  const { t } = useTranslation();

  return (
    <Dialog open={open} onClose={onCancel}>
      <DialogTitle>{t('tsxAnalystPresence.status.confirmDialog.title')}</DialogTitle>
      <DialogContent>
        <DialogContentText>
          {status === null
            ? t('tsxAnalystPresence.status.confirmDialog.clearMessage', { username })
            : t('tsxAnalystPresence.status.confirmDialog.changeMessage', { username, status })}
        </DialogContentText>
      </DialogContent>
      <DialogActions>
        <Button color="secondary" onClick={onCancel} autoFocus>
          {t('tsxAnalystPresence.common.cancel')}
        </Button>
        <Button color="secondary" onClick={onConfirm}>
          {t('tsxAnalystPresence.common.confirm')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
