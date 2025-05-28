import { Button, Stack, TextField, Typography } from '@mui/material';
import { parseEvent } from 'commons/components/utils/keyboard';
import { ModalContext } from 'components/app/providers/ModalProvider';
import type { FC } from 'react';
import { useCallback, useContext, useState } from 'react';
import { useTranslation } from 'react-i18next';

const RationaleModal: FC<{ onSubmit: (rationale: string) => void }> = ({ onSubmit }) => {
  const { t } = useTranslation();
  const { close } = useContext(ModalContext);

  const [rationale, setRationale] = useState('');

  const handleSubmit = useCallback(() => {
    onSubmit(rationale);
    close();
  }, [onSubmit, rationale, close]);

  const handleKeydown = useCallback(
    e => {
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
      <Typography variant="h4">{t('modal.rationale.title')}</Typography>
      <Typography>{t('modal.rationale.description')}</Typography>
      <TextField
        label={t('modal.rationale.label')}
        value={rationale}
        // eslint-disable-next-line jsx-a11y/no-autofocus
        autoFocus
        fullWidth
        multiline
        maxRows={6}
        onChange={e => setRationale(e.target.value)}
        onKeyDown={handleKeydown}
      />
      <Stack direction="row" spacing={1} alignSelf="end">
        <Button variant="outlined" onClick={close}>
          {t('cancel')}
        </Button>
        <Button variant="outlined" onClick={handleSubmit}>
          {t('submit')}
        </Button>
      </Stack>
    </Stack>
  );
};

export default RationaleModal;
