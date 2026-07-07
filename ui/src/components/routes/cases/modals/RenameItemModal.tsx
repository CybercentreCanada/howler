import { Button, CircularProgress, Stack, TextField, Typography } from '@mui/material';
import api from 'api';
import { ModalContext } from 'components/app/providers/ModalProvider';
import useMyApi from 'components/hooks/useMyApi';
import type { Case } from 'models/entities/generated/Case';
import type { Item } from 'models/entities/generated/Item';
import { useContext, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';

const RenameItemModal: FC<{ _case: Case; leaf: Item; onRenamed?: (updatedCase: Case) => void }> = ({
  _case,
  leaf,
  onRenamed
}) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const { close } = useContext(ModalContext);

  const currentName = leaf.name ?? leaf.value ?? '';

  const [name, setName] = useState(currentName);
  const [submitting, setSubmitting] = useState(false);
  const nameError = useMemo<string | null>(() => {
    if (!name.trim()) {
      return t('modal.cases.rename_item.error.empty');
    }
    return null;
  }, [name, t]);

  const isValid = !nameError;

  const onSubmit = async () => {
    if (!isValid || !_case.case_id || !leaf.id) {
      return;
    }
    setSubmitting(true);
    try {
      const updatedCase = await dispatchApi(api.v2.case.items.rename(_case.case_id, leaf.id, name.trim()));
      if (updatedCase) {
        onRenamed?.(updatedCase);
        close();
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Stack spacing={2} p={2} sx={{ minWidth: 'min(600px, 60vw)' }}>
      <Typography variant="h4">{t('modal.cases.rename_item')}</Typography>
      <TextField
        size="small"
        label={t('modal.cases.rename_item.new_name')}
        value={name}
        onChange={ev => setName(ev.target.value)}
        error={!!nameError}
        helperText={nameError ?? ' '}
        fullWidth
        autoFocus
        onKeyDown={ev => {
          if (ev.key === 'Enter' && isValid && !submitting) {
            onSubmit();
          }
        }}
      />
      <Stack direction="row" justifyContent="flex-end" spacing={1}>
        <Button onClick={close} color="error" variant="outlined" disabled={submitting}>
          {t('button.cancel')}
        </Button>
        <Button
          onClick={onSubmit}
          color="success"
          variant="outlined"
          disabled={!isValid || submitting}
          startIcon={submitting ? <CircularProgress size={16} color="inherit" /> : undefined}
        >
          {t('button.confirm')}
        </Button>
      </Stack>
    </Stack>
  );
};

export default RenameItemModal;
