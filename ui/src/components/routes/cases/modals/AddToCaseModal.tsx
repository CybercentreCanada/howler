import { Autocomplete, Button, Stack, TextField, Typography } from '@mui/material';
import api from 'api';
import { ModalContext } from 'components/app/providers/ModalProvider';
import CaseCard from 'components/elements/case/CaseCard';
import useMyApi from 'components/hooks/useMyApi';
import type { Case } from 'models/entities/generated/Case';
import type { Hit } from 'models/entities/generated/Hit';
import type { Observable } from 'models/entities/generated/Observable';
import { useContext, useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';

const AddToCaseModal: FC<{ records: (Hit | Observable)[] }> = ({ records }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const { close } = useContext(ModalContext);

  const [cases, setCases] = useState<Case[]>([]);
  const [selectedCase, setSelectedCase] = useState<Case | null>(null);
  const [path, setPath] = useState('');
  const [title, setTitle] = useState('');

  useEffect(() => {
    dispatchApi(api.search.case.post({ query: 'case_id:*', rows: 100 }), { throwError: false }).then(result => {
      if (result) {
        setCases(result.items);
      }
    });
  }, [dispatchApi]);

  const folderOptions = useMemo<string[]>(() => {
    if (!selectedCase?.items) {
      return [];
    }

    const paths = new Set<string>();

    for (const item of selectedCase.items) {
      if (!item.path) {
        continue;
      }

      const parts = item.path.split('/');
      parts.pop();

      for (let i = 1; i <= parts.length; i++) {
        paths.add(parts.slice(0, i).join('/'));
      }
    }

    return Array.from(paths).sort();
  }, [selectedCase]);

  const fullPath = path ? `${path}/${title}` : title;
  const isValid = !!selectedCase && !!title;

  const onSubmit = async () => {
    if (!selectedCase || records?.length < 1) {
      return;
    }

    await dispatchApi(
      api.v2.case.items.post(selectedCase.case_id, {
        path: fullPath,
        value: records[0].howler.id,
        type: records[0].__index
      })
    );

    close();
  };

  // TODO: No support currently for multiple records

  return (
    <Stack spacing={2} p={2} sx={{ minWidth: 'min(800px, 60vw)', height: '100%' }}>
      <Typography variant="h4">{t('modal.cases.add_to_case')}</Typography>
      <Autocomplete<Case>
        options={cases}
        getOptionLabel={option => option.title ?? option.case_id ?? ''}
        isOptionEqualToValue={(option, value) => option.case_id === value.case_id}
        value={selectedCase}
        disablePortal
        onChange={(_ev, newVal) => {
          setSelectedCase(newVal);
          setPath('');
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
      {selectedCase && (
        <>
          <Autocomplete
            freeSolo
            disablePortal
            options={folderOptions}
            value={path}
            onInputChange={(_ev, newVal) => setPath(newVal)}
            renderInput={params => (
              <TextField {...params} size="small" placeholder={t('modal.cases.add_to_case.select_path')} fullWidth />
            )}
          />
          <TextField
            size="small"
            placeholder={t('modal.cases.add_to_case.title')}
            value={title}
            onChange={ev => setTitle(ev.target.value)}
            fullWidth
          />
          {title && (
            <Typography variant="caption" color="textSecondary">
              {t('modal.cases.add_to_case.full_path', { path: fullPath })}
            </Typography>
          )}
        </>
      )}
      <div style={{ flex: 1 }} />
      <Stack direction="row" spacing={1} alignSelf="end">
        <Button variant="outlined" color="error" onClick={close}>
          {t('cancel')}
        </Button>
        <Button variant="outlined" color="success" disabled={!isValid} onClick={onSubmit}>
          {t('confirm')}
        </Button>
      </Stack>
    </Stack>
  );
};

export default AddToCaseModal;
