import { Button, Stack, Typography } from '@mui/material';
import { ModalContext } from 'components/app/providers/ModalProvider';
import type { FC } from 'react';
import { useCallback, useContext } from 'react';
import { useTranslation } from 'react-i18next';

const ConfirmDeleteModal: FC<{
  onConfirm: () => void;
  title?: string;
  description?: string;
  preferDelete?: boolean;
  preferCancel?: boolean;
}> = ({ onConfirm, title, description, preferDelete, preferCancel }) => {
  const { t } = useTranslation();
  const { close } = useContext(ModalContext);

  const handleConfirm = useCallback(() => {
    onConfirm();
    close();
  }, [close, onConfirm]);

  const modalTitle = title ?? t('modal.confirm.delete.title');
  const modalDesc = description ?? t('modal.confirm.delete.description');

  return (
    <Stack spacing={2} p={2} alignItems="start" sx={{ minWidth: '500px' }}>
      <Typography variant="h4">{modalTitle}</Typography>
      <Typography>{modalDesc}</Typography>
      <Stack direction="row" spacing={1} alignSelf="end">
        <Button variant={preferCancel ? 'contained' : 'outlined'} onClick={close}>
          {t('button.cancel')}
        </Button>
        <Button variant={preferDelete ? 'contained' : 'outlined'} onClick={handleConfirm}>
          {t('button.delete')}
        </Button>
      </Stack>
    </Stack>
  );
};

export default ConfirmDeleteModal;
