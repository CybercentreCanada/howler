import { Autocomplete, Button, CircularProgress, Divider, Stack, TextField, Typography } from '@mui/material';
import api from 'api';
import { ModalContext } from 'components/app/providers/ModalProvider';
import CaseCard from 'components/elements/case/CaseCard';
import useMyApi from 'components/hooks/useMyApi';
import type { Case } from 'models/entities/generated/Case';
import type { Hit } from 'models/entities/generated/Hit';
import type { Observable } from 'models/entities/generated/Observable';
import { useContext, useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import CaseRecordRow from './CaseRecordRow';
import { useFolderOptions, useRecordEntries } from './hooks';

// ---------------------------------------------------------------------------
// Modal
// ---------------------------------------------------------------------------

const AddToCaseModal: FC<{ records: (Hit | Observable)[] }> = ({ records }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const { close } = useContext(ModalContext);

  const [cases, setCases] = useState<Case[]>([]);
  const [selectedCase, setSelectedCase] = useState<Case | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [entries, updateEntry] = useRecordEntries(records);

  useEffect(() => {
    dispatchApi(api.search.case.post({ query: 'case_id:*', rows: 100 }), { throwError: false }).then(result => {
      if (result) {
        setCases(result.items);
      }
    });
  }, [dispatchApi]);

  const folderOptions = useFolderOptions(selectedCase);

  const isValid = useMemo(
    () =>
      !!selectedCase &&
      entries.length > 0 &&
      entries.every(e => !!e.title.trim() && !e.path.startsWith('/') && !e.path.endsWith('/')),
    [selectedCase, entries]
  );

  const onSubmit = async () => {
    if (!isValid || !selectedCase) {
      return;
    }

    setSubmitting(true);
    try {
      for (const entry of entries) {
        const fullPath = entry.path ? `${entry.path}/${entry.title}` : entry.title;
        await dispatchApi(
          api.v2.case.items.post(selectedCase.case_id, {
            path: fullPath,
            value: entry.record.howler.id,
            type: entry.record.__index
          })
        );
      }

      close();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Stack spacing={2} p={2} sx={{ minWidth: 'min(800px, 60vw)', maxHeight: '90vh', height: '100%' }}>
      <Typography variant="h4">{t('modal.cases.add_to_case')}</Typography>
      <Autocomplete<Case>
        options={cases}
        getOptionLabel={option => option.title ?? option.case_id ?? ''}
        isOptionEqualToValue={(option, value) => option.case_id === value.case_id}
        value={selectedCase}
        disablePortal
        onChange={(_ev, newVal) => {
          setSelectedCase(newVal);
        }}
        renderOption={(props, option) => (
          <li
            {...props}
            key={option.case_id}
            style={{ ...props.style, display: 'flex', justifyContent: 'stretch', alignItems: 'stretch' }}
          >
            <CaseCard case={option} slotProps={{ card: { sx: { width: '100%' } } }} />
          </li>
        )}
        renderInput={params => (
          <TextField {...params} size="small" placeholder={t('modal.cases.add_to_case.select_case')} fullWidth />
        )}
      />
      {selectedCase && entries.length > 0 ? (
        <>
          <Divider>
            <Typography variant="caption" color="textSecondary">
              {t('modal.cases.add_to_case.items_section')}
            </Typography>
          </Divider>
          <Stack spacing={1} overflow="auto" flex={1}>
            {entries.map((entry, i) => (
              <CaseRecordRow
                key={entry.record.howler.id}
                entry={entry}
                folderOptions={folderOptions}
                onTitleChange={val => updateEntry(i, 'title', val)}
                onPathChange={val => updateEntry(i, 'path', val)}
              />
            ))}
          </Stack>
        </>
      ) : (
        <div style={{ flex: 1, maxHeight: '100px' }} />
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
