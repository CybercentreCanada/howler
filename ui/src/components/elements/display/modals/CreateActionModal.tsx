import { Button, Stack, TextField, Typography } from '@mui/material';
import { parseEvent } from 'commons/components/utils/keyboard';
import { ModalContext } from 'components/app/providers/ModalProvider';
import useMySnackbar from 'components/hooks/useMySnackbar';
import type { FC, KeyboardEvent } from 'react';
import { useCallback, useContext, useState } from 'react';
import { useTranslation } from 'react-i18next';

const CreateActionModal: FC<{ onSubmit: (rationale: string) => void }> = ({ onSubmit }) => {
  const { t } = useTranslation();
  const { close } = useContext(ModalContext);
  const { showInfoMessage } = useMySnackbar();

  const [actionName, setActionName] = useState('');

  const handleSubmit = useCallback(() => {
    if (actionName) {
      onSubmit(actionName);
      close();
    } else {
      showInfoMessage(t('modal.action.empty'));
    }
  }, [actionName, onSubmit, close, showInfoMessage, t]);

  const handleKeydown = useCallback(
    (e: KeyboardEvent<HTMLElement>) => {
      const parsedEvent = parseEvent(e);

      if (parsedEvent.isCtrl && parsedEvent.isEnter) {
        handleSubmit();
      } else if (parsedEvent.isEscape) {
        close();
      }
    },
    [close, handleSubmit]
  );

  return (
    <Stack spacing={2} p={2} alignItems="start" sx={{ minWidth: '500px' }}>
      <Typography variant="h4">{t('modal.action.title')}</Typography>
      <Typography>{t('modal.action.description')}</Typography>
      <TextField
        label={t('modal.action.label')}
        value={actionName}
        // eslint-disable-next-line jsx-a11y/no-autofocus
        autoFocus
        fullWidth
        onChange={e => setActionName(e.target.value)}
        onKeyDown={handleKeydown}
      />
      <Stack direction="row" spacing={1} alignSelf="end">
        <Button variant="outlined" onClick={close}>
          {t('cancel')}
        </Button>
        <Button disabled={!actionName} variant="outlined" onClick={handleSubmit}>
          {t('submit')}
        </Button>
      </Stack>
    </Stack>
  );
};

export default CreateActionModal;
