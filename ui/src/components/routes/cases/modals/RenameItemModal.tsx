import { Button, Stack, TextField, Typography } from '@mui/material';
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

  const currentPath = leaf.path ?? '';
  const lastSlash = currentPath.lastIndexOf('/');
  const folderPrefix = lastSlash >= 0 ? currentPath.slice(0, lastSlash) : '';
  const currentName = lastSlash >= 0 ? currentPath.slice(lastSlash + 1) : currentPath;

  const [name, setName] = useState(currentName);

  const newPath = folderPrefix ? `${folderPrefix}/${name}` : name;

  const existingPaths = useMemo(
    () => new Set((_case.items ?? []).filter(item => item.value !== leaf.value).map(item => item.path)),
    [_case.items, leaf.value]
  );

  const nameError = useMemo<string | null>(() => {
    if (!name.trim()) {
      return t('modal.cases.rename_item.error.empty');
    }
    if (name.includes('/')) {
      return t('modal.cases.rename_item.error.slash');
    }
    if (existingPaths.has(newPath)) {
      return t('modal.cases.rename_item.error.taken');
    }
    return null;
  }, [name, newPath, existingPaths, t]);

  const isValid = !nameError;

  const onSubmit = async () => {
    if (!isValid || !_case.case_id || !leaf.value) {
      return;
    }
    const updatedCase = await dispatchApi(api.v2.case.items.put(_case.case_id, leaf.value, newPath));
    if (updatedCase) {
      onRenamed?.(updatedCase);
      close();
    }
  };

  return (
    <Stack spacing={2} p={2} sx={{ minWidth: 'min(600px, 60vw)' }}>
      <Typography variant="h4">{t('modal.cases.rename_item')}</Typography>
      {folderPrefix && (
        <Typography variant="body2" color="textSecondary">
          {t('modal.cases.rename_item.folder_path', { path: folderPrefix })}
        </Typography>
      )}
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
          if (ev.key === 'Enter' && isValid) {
            onSubmit();
          }
        }}
      />
      <Stack direction="row" justifyContent="flex-end" spacing={1}>
        <Button onClick={close} color="error" variant="outlined">
          {t('button.cancel')}
        </Button>
        <Button onClick={onSubmit} color="success" variant="outlined" disabled={!isValid}>
          {t('button.confirm')}
        </Button>
      </Stack>
    </Stack>
  );
};

export default RenameItemModal;
