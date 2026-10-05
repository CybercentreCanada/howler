import { Add, Delete } from '@mui/icons-material';
import {
  Autocomplete,
  Box,
  Button,
  CircularProgress,
  Divider,
  IconButton,
  Stack,
  TextField,
  Typography
} from '@mui/material';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import api from 'api';
import type { SearchField } from 'api/search/fields';
import { ModalContext } from 'components/app/providers/ModalProvider';
import useMyApi from 'components/hooks/useMyApi';
import type { Dayjs } from 'dayjs';
import { unflatten } from 'flat';
import Fuse from 'fuse.js';
import type { Case } from 'models/entities/generated/Case';
import { useContext, useEffect, useMemo, useState, type FC, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { useFolderOptions } from './hooks';

const ESCALATIONS = ['hit', 'alert', 'evidence'];
const MANAGED_FIELDS = new Set([
  'event.created',
  'event.id',
  'event.ingested',
  'event.kind',
  'event.provider',
  'howler.escalation',
  'howler.hash',
  'howler.id',
  'howler.outline.indicators',
  'howler.outline.summary',
  'howler.outline.target',
  'howler.outline.threat',
  'howler.related',
  'message',
  'classification',
  'timestamp'
]);

type AddEventModalProps = {
  case: Case;
  parentId?: string;
  onUpdated?: (updatedCase: Case) => void;
};

type FieldValue = string | number | boolean | string[] | number[];
type CaseWithClassification = Case & { classification?: string };

const isBlank = (value: unknown) => {
  if (Array.isArray(value)) {
    return value.length === 0;
  }

  return value === undefined || value === null || (typeof value === 'string' && value.trim() === '');
};

const getFieldOptions = (fields: SearchField[]) =>
  fields.filter(field => {
    const key = field.key ?? '';
    return (
      key &&
      !MANAGED_FIELDS.has(key) &&
      field.type !== 'object' &&
      !key.startsWith('howler.comment.') &&
      !key.startsWith('howler.log.')
    );
  });

const parseList = (value: string): string[] =>
  value
    .split(/[\n,]/)
    .map(entry => entry.trim())
    .filter(Boolean);

const searchFields = (fields: SearchField[], query: string): SearchField[] => {
  if (!query.trim()) {
    return fields;
  }

  const tokens = query.toLowerCase().trim().split(/\s+/);
  const tokenMatches = fields.filter(field => {
    const searchable = `${field.key ?? ''} ${field.description ?? ''}`.toLowerCase();
    return tokens.every(token => searchable.includes(token));
  });
  const fuzzyMatches = new Fuse(fields, {
    keys: ['key', 'description'],
    ignoreLocation: true,
    threshold: 0.4
  })
    .search(query)
    .map(result => result.item);

  return [...tokenMatches, ...fuzzyMatches.filter(field => !tokenMatches.includes(field))];
};

const FieldInput: FC<{
  field: SearchField;
  value: FieldValue | undefined;
  onChange: (value: FieldValue | undefined) => void;
}> = ({ field, value, onChange }) => {
  const label = field.key ?? '';
  const values = field.values ?? [];

  if (values.length > 0) {
    if (field.list) {
      return (
        <Autocomplete
          multiple
          options={values}
          value={Array.isArray(value) ? value.map(String) : []}
          onChange={(_, nextValue) => onChange(nextValue)}
          renderInput={params => <TextField {...params} size="small" label={label} helperText={field.description} />}
        />
      );
    }

    return (
      <Autocomplete
        options={values}
        value={typeof value === 'string' ? value : null}
        onChange={(_, nextValue) => onChange(nextValue ?? undefined)}
        renderInput={params => <TextField {...params} size="small" label={label} helperText={field.description} />}
      />
    );
  }

  if (field.type === 'boolean') {
    return (
      <Autocomplete
        options={['true', 'false']}
        value={typeof value === 'boolean' ? String(value) : null}
        onChange={(_, nextValue) => onChange(nextValue === null ? undefined : nextValue === 'true')}
        renderInput={params => <TextField {...params} size="small" label={label} helperText={field.description} />}
      />
    );
  }

  if (field.list) {
    return (
      <TextField
        size="small"
        label={label}
        helperText={field.description ?? 'Enter one value per line.'}
        value={Array.isArray(value) ? value.join('\n') : ''}
        onChange={event => onChange(parseList(event.target.value))}
        multiline
      />
    );
  }

  const numeric = ['integer', 'long', 'float', 'double', 'number'].includes(field.type);

  return (
    <TextField
      size="small"
      label={label}
      type={numeric ? 'number' : 'text'}
      helperText={field.description}
      value={value === undefined ? '' : String(value)}
      onChange={event => {
        const nextValue = event.target.value;
        if (!nextValue) {
          onChange(undefined);
        } else if (numeric) {
          onChange(
            field.type === 'integer' || field.type === 'long' ? Number.parseInt(nextValue, 10) : Number(nextValue)
          );
        } else {
          onChange(nextValue);
        }
      }}
    />
  );
};

const AddEventModal: FC<AddEventModalProps> = ({ case: _case, parentId, onUpdated }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const { close } = useContext(ModalContext);

  const [fields, setFields] = useState<SearchField[]>([]);
  const [selectedFields, setSelectedFields] = useState<SearchField[]>([]);
  const [fieldValues, setFieldValues] = useState<Record<string, FieldValue | undefined>>({});
  const [fieldSearch, setFieldSearch] = useState('');
  const [title, setTitle] = useState('');
  const [created, setCreated] = useState<Dayjs | null>(null);
  const [provider, setProvider] = useState('');
  const [escalation, setEscalation] = useState<string | null>(null);
  const [target, setTarget] = useState('');
  const [threat, setThreat] = useState('');
  const [indicators, setIndicators] = useState('');
  const [summary, setSummary] = useState('');
  const [selectedParent, setSelectedParent] = useState<string | undefined>(parentId);
  const [createdEventId, setCreatedEventId] = useState<string | undefined>();
  const [submitting, setSubmitting] = useState(false);

  const folderOptions = useFolderOptions(_case);

  useEffect(() => {
    void dispatchApi(api.search.fields.event.get(), { throwError: false }).then(result => {
      if (result) {
        setFields(getFieldOptions(result));
      }
    });
  }, [dispatchApi]);

  const filteredFields = useMemo(() => searchFields(fields, fieldSearch), [fieldSearch, fields]);

  const hasOutlineValue = Boolean(target.trim() || threat.trim() || parseList(indicators).length);
  const isValid = Boolean(title.trim() && created?.isValid() && provider.trim() && escalation && hasOutlineValue);

  const setOptionalField = (field: SearchField) => {
    if (!field.key || selectedFields.some(selected => selected.key === field.key)) {
      return;
    }

    setSelectedFields(current => [...current, field]);
    setFieldSearch('');
  };

  const removeOptionalField = (key: string) => {
    setSelectedFields(current => current.filter(field => field.key !== key));
    setFieldValues(current => {
      return Object.fromEntries(Object.entries(current).filter(([fieldKey]) => fieldKey !== key));
    });
  };

  const buildPayload = () => {
    const payload: Record<string, unknown> = {
      classification: (_case as CaseWithClassification).classification,
      message: title.trim(),
      'event.created': created!.toISOString(),
      'event.kind': 'event',
      'event.provider': provider.trim(),
      'howler.escalation': escalation,
      'howler.outline.indicators': parseList(indicators)
    };

    if (target.trim()) {
      payload['howler.outline.target'] = target.trim();
    }
    if (threat.trim()) {
      payload['howler.outline.threat'] = threat.trim();
    }
    if (summary.trim()) {
      payload['howler.outline.summary'] = summary.trim();
    }
    for (const field of selectedFields) {
      const value = field.key ? fieldValues[field.key] : undefined;
      if (field.key && !isBlank(value)) {
        payload[field.key] = value;
      }
    }

    return unflatten(payload) as Record<string, unknown>;
  };

  const onSubmit = async () => {
    if (!isValid || !_case.case_id) {
      return;
    }

    setSubmitting(true);
    try {
      let eventId = createdEventId;
      if (!eventId) {
        const ids = await dispatchApi(api.v2.ingest.post('event', [buildPayload()], 'wait_for'));
        eventId = ids?.[0];
        if (!eventId) {
          throw new Error(t('modal.cases.add_event.error.no_id'));
        }
        setCreatedEventId(eventId);
      }

      const updatedCase = await dispatchApi(
        api.v2.case.items.post(_case.case_id, {
          type: 'event',
          value: eventId,
          name: title.trim(),
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

  const renderField = (field: SearchField): ReactNode => {
    if (!field.key) {
      return null;
    }

    return (
      <Stack key={field.key} direction="row" spacing={1} alignItems="flex-start">
        <Box flex={1}>
          <FieldInput
            field={field}
            value={fieldValues[field.key]}
            onChange={value => setFieldValues(current => ({ ...current, [field.key!]: value }))}
          />
        </Box>
        <IconButton
          aria-label={t('modal.cases.add_event.remove_field')}
          onClick={() => removeOptionalField(field.key!)}
        >
          <Delete />
        </IconButton>
      </Stack>
    );
  };

  return (
    <Stack spacing={2} p={2} sx={{ minWidth: 'min(900px, 70vw)', maxHeight: '90vh', height: '100%' }}>
      <Typography variant="h4">{t('modal.cases.add_event')}</Typography>

      <Stack spacing={1} alignItems="stretch">
        <TextField
          required
          size="small"
          label={t('modal.cases.add_event.title')}
          value={title}
          onChange={event => setTitle(event.target.value)}
          fullWidth
        />
        <Stack direction="row" spacing={1}>
          <LocalizationProvider dateAdapter={AdapterDayjs}>
            <DateTimePicker
              value={created}
              onChange={setCreated}
              ampm={false}
              slotProps={{
                textField: { required: true, size: 'small', fullWidth: true },
                dialog: { disablePortal: true },
                popper: { disablePortal: true }
              }}
              label={t('modal.cases.add_event.created')}
            />
          </LocalizationProvider>

          <Autocomplete
            fullWidth
            disablePortal
            options={ESCALATIONS}
            value={escalation}
            onChange={(_, value) => setEscalation(value)}
            renderInput={params => (
              <TextField {...params} required size="small" label={t('modal.cases.add_event.escalation')} />
            )}
          />
        </Stack>
        <TextField
          required
          size="small"
          label={t('modal.cases.add_event.provider')}
          value={provider}
          onChange={event => setProvider(event.target.value)}
          fullWidth
        />
        <TextField
          size="small"
          label={t('modal.cases.add_event.summary')}
          value={summary}
          onChange={event => setSummary(event.target.value)}
        />

        {folderOptions.length > 0 && (
          <Autocomplete
            disablePortal
            options={folderOptions}
            getOptionLabel={option => option.label}
            value={folderOptions.find(folder => folder.id === selectedParent) ?? null}
            onChange={(_, value) => setSelectedParent(value?.id)}
            renderInput={params => <TextField {...params} size="small" label={t('modal.cases.add_item.folder')} />}
          />
        )}
        <Typography variant="caption" color="textSecondary">
          {t('modal.cases.add_event.outline_required')}
        </Typography>
        <Stack direction="row" spacing={1}>
          <TextField
            fullWidth
            size="small"
            label={t('modal.cases.add_event.target')}
            value={target}
            onChange={event => setTarget(event.target.value)}
          />
          <TextField
            fullWidth
            size="small"
            label={t('modal.cases.add_event.threat')}
            value={threat}
            onChange={event => setThreat(event.target.value)}
          />
        </Stack>
        <TextField
          size="small"
          multiline
          label={t('modal.cases.add_event.indicators')}
          value={indicators}
          onChange={event => setIndicators(event.target.value)}
          helperText={t('modal.cases.add_event.indicators_help')}
        />
      </Stack>

      <Divider>
        <Typography variant="caption">{t('modal.cases.add_event.additional_fields')}</Typography>
      </Divider>
      <Autocomplete
        disablePortal
        options={filteredFields}
        filterOptions={options => options}
        inputValue={fieldSearch}
        onInputChange={(_, value) => setFieldSearch(value)}
        value={null}
        onChange={(_, field) => field && setOptionalField(field)}
        getOptionLabel={field => field.key ?? ''}
        isOptionEqualToValue={(option, value) => option.key === value.key}
        renderOption={(props, field) => (
          <Box component="li" {...props} key={field.key}>
            <Stack>
              <Typography variant="body2">{field.key}</Typography>
              <Typography variant="caption" color="text.secondary">
                {field.type} {field.description ? `- ${field.description}` : ''}
              </Typography>
            </Stack>
          </Box>
        )}
        renderInput={params => <TextField {...params} size="small" label={t('modal.cases.add_event.search_fields')} />}
      />
      {selectedFields.length > 0 && (
        <Stack spacing={1} overflow="auto" flex={1} pt={1}>
          {selectedFields.map(renderField)}
        </Stack>
      )}

      <Stack direction="row" spacing={1} alignSelf="end">
        <Button variant="outlined" color="error" onClick={close} disabled={submitting}>
          {t('cancel')}
        </Button>
        <Button
          variant="outlined"
          color="success"
          disabled={!isValid || submitting}
          startIcon={submitting ? <CircularProgress size={16} color="inherit" /> : <Add />}
          onClick={onSubmit}
        >
          {t('modal.cases.add_event.submit')}
        </Button>
      </Stack>
    </Stack>
  );
};

export default AddEventModal;
