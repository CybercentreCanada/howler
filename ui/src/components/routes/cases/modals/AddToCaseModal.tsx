import { useMonaco } from '@monaco-editor/react';
import { Autocomplete, Box, Button, CircularProgress, Stack, TextField, Typography, useTheme } from '@mui/material';
import api from 'api';
import { ModalContext } from 'components/app/providers/ModalProvider';
import ThemedEditor from 'components/elements/ThemedEditor';
import useMyApi from 'components/hooks/useMyApi';
import type { Case } from 'models/entities/generated/Case';
import { useContext, useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useFolderOptions } from './hooks';

const ITEM_TYPES = [
  { value: 'reference', labelKey: 'modal.cases.add_item.type.link' },
  { value: 'markdown', labelKey: 'modal.cases.add_item.type.markdown' }
] as const;

interface AddItemToCaseModalProps {
  case: Case;
  parentId?: string | null;
  onUpdated?: (updatedCase: Case) => void;
}

const AddToCaseModal: FC<AddItemToCaseModalProps> = ({ case: _case, parentId = null, onUpdated }) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const monaco = useMonaco();
  const { dispatchApi } = useMyApi();
  const { close } = useContext(ModalContext);

  const [itemType, setItemType] = useState<(typeof ITEM_TYPES)[number]>(ITEM_TYPES[0]);
  const [title, setTitle] = useState('');
  const [value, setValue] = useState('');
  const [selectedParent, setSelectedParent] = useState<string | null>(parentId);
  const [submitting, setSubmitting] = useState(false);

  const folderOptions = useFolderOptions(_case);

  useEffect(() => {
    if (!monaco) {
      return;
    }

    monaco.editor.getModels().forEach(model => model.setEOL(monaco.editor.EndOfLineSequence.LF));
  }, [monaco]);

  const isValid = useMemo(() => {
    if (!title.trim()) {
      return false;
    }
    if (itemType.value === 'reference' && !value.trim()) {
      return false;
    }
    if (itemType.value === 'markdown' && !value.trim()) {
      return false;
    }
    return true;
  }, [title, value, itemType]);

  const onSubmit = async () => {
    if (!isValid || !_case.case_id) {
      return;
    }

    setSubmitting(true);
    try {
      const updatedCase = await dispatchApi(
        api.v2.case.items.post(_case.case_id, {
          type: itemType.value,
          value,
          name: title,
          parent: selectedParent
        })
      );
      if (updatedCase) {
        onUpdated?.(updatedCase);
        close();
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Stack spacing={2} p={2} sx={{ minWidth: 'min(1000px, 60vw)' }}>
      <Typography variant="h4">{t('modal.cases.add_item')}</Typography>

      <Stack direction="row" spacing={1}>
        <Autocomplete
          value={itemType}
          onChange={(_, option) => {
            if (option) {
              setItemType(option);
            }
          }}
          options={ITEM_TYPES}
          getOptionLabel={opt => t(opt.labelKey)}
          isOptionEqualToValue={(option, choice) => option.value === choice.value}
          disablePortal
          disableClearable
          renderInput={params => (
            <TextField {...params} size="small" label={t('modal.cases.add_item.type')} sx={{ minWidth: '175px' }} />
          )}
        />

        <TextField
          size="small"
          label={t('modal.cases.add_item.title')}
          value={title}
          onChange={ev => setTitle(ev.target.value)}
          fullWidth
          autoFocus
        />
      </Stack>

      {itemType.value === 'reference' && (
        <TextField
          size="small"
          label={t('modal.cases.add_item.url')}
          value={value}
          onChange={ev => setValue(ev.target.value)}
          fullWidth
          placeholder="https://example.com"
        />
      )}

      {itemType.value === 'markdown' && (
        <Box sx={{ border: 'thin solid', borderColor: theme.palette.divider }}>
          <ThemedEditor
            id="add-item-markdown"
            height="240px"
            width="100%"
            language="markdown"
            theme={theme.palette.mode === 'light' ? 'howler' : 'howler-dark'}
            value={value}
            onChange={content => setValue(content ?? '')}
            options={{}}
          />
        </Box>
      )}

      {folderOptions.length > 0 && (
        <Autocomplete
          options={folderOptions}
          getOptionLabel={opt => opt.label}
          isOptionEqualToValue={(opt, val) => opt.id === val.id}
          value={folderOptions.find(f => f.id === selectedParent) ?? null}
          disablePortal
          onChange={(_ev, newVal) => setSelectedParent(newVal?.id ?? null)}
          renderInput={params => (
            <TextField
              {...params}
              size="small"
              label={t('modal.cases.add_item.folder')}
              placeholder={t('modal.cases.add_item.root')}
              fullWidth
            />
          )}
        />
      )}

      <Stack direction="row" spacing={1} alignSelf="end">
        <Button variant="outlined" color="error" onClick={close} disabled={submitting}>
          {t('cancel')}
        </Button>
        <Button
          variant="outlined"
          color="success"
          disabled={!isValid || submitting}
          startIcon={submitting ? <CircularProgress size={16} color="inherit" /> : undefined}
          onClick={onSubmit}
        >
          {t('confirm')}
        </Button>
      </Stack>
    </Stack>
  );
};

export default AddToCaseModal;
