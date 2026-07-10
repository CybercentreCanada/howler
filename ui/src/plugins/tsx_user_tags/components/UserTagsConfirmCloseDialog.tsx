import { Button, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle } from '@mui/material';
import { useTranslation } from 'react-i18next';

type UserTagsConfirmCloseDialogProps = {
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export const UserTagsConfirmCloseDialog = ({ open, onConfirm, onCancel }: UserTagsConfirmCloseDialogProps) => {
  const { t } = useTranslation();

  return (
    <Dialog open={open} onClose={onCancel}>
      <DialogTitle>{t('tsxUserTags.drawer.confirmCloseDialog.title')}</DialogTitle>
      <DialogContent>
        <DialogContentText>{t('tsxUserTags.drawer.confirmCloseDialog.message')}</DialogContentText>
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel} color="secondary" autoFocus>
          {t('tsxUserTags.drawer.confirmCloseDialog.cancelButton')}
        </Button>
        <Button onClick={onConfirm} color="error">
          {t('tsxUserTags.drawer.confirmCloseDialog.confirmButton')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
