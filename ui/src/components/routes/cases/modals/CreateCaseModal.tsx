import { Autocomplete, Button, CircularProgress, Divider, Stack, TextField, Typography } from '@mui/material';
import api from 'api';
import { ModalContext } from 'components/app/providers/ModalProvider';
import MarkdownEditor from 'components/elements/MarkdownEditor';
import useMyApi from 'components/hooks/useMyApi';
import type { Hit } from 'models/entities/generated/Hit';
import type { Observable } from 'models/entities/generated/Observable';
import { useContext, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import CaseRecordRow from './CaseRecordRow';
import { useRecordEntries } from './hooks';

const ESCALATIONS = ['normal', 'focus', 'crisis'];

const CreateCaseModal: FC<{ records: (Hit | Observable)[] }> = ({ records }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const { close } = useContext(ModalContext);

  const [caseTitle, setCaseTitle] = useState('');
  const [summary, setSummary] = useState('');
  const [overview, setOverview] = useState('');
  const [escalation, setEscalation] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [entries, updateEntry] = useRecordEntries(records);

  const isValid = useMemo(
    () => !!caseTitle.trim() && !!summary.trim() && entries.every(e => !!e.title.trim()),
    [caseTitle, summary, entries]
  );

  const onSubmit = async () => {
    if (!isValid) {
      return;
    }

    setSubmitting(true);
    try {
      const newCase = await dispatchApi(
        api.v2.case.post({
          title: caseTitle.trim(),
          summary: summary.trim(),
          ...(overview.trim() ? { overview: overview.trim() } : {}),
          ...(escalation ? { escalation } : {})
        })
      );

      if (newCase?.case_id) {
        for (const entry of entries) {
          const fullPath = entry.path ? `${entry.path}/${entry.title}` : entry.title;
          await dispatchApi(
            api.v2.case.items.post(newCase.case_id, {
              path: fullPath,
              value: entry.record.howler.id,
              type: entry.record.__index
            })
          );
        }

        close();
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Stack spacing={2} p={2} sx={{ minWidth: 'min(800px, 60vw)', maxHeight: '90vh', height: '100%' }}>
      <Typography variant="h4">{t('modal.cases.create_case')}</Typography>

      {/* Case metadata */}
      <Stack spacing={1}>
        <TextField
          size="small"
          fullWidth
          placeholder={t('modal.cases.create_case.title')}
          value={caseTitle}
          onChange={ev => setCaseTitle(ev.target.value)}
        />
        <TextField
          size="small"
          fullWidth
          placeholder={t('modal.cases.create_case.summary')}
          value={summary}
          onChange={ev => setSummary(ev.target.value)}
        />
        <Autocomplete
          options={ESCALATIONS}
          value={escalation}
          disablePortal
          onChange={(_ev, val) => setEscalation(val)}
          renderInput={params => (
            <TextField {...params} size="small" placeholder={t('modal.cases.create_case.escalation')} fullWidth />
          )}
        />
        <Stack spacing={0.5}>
          <Typography variant="caption" color="textSecondary">
            {t('modal.cases.create_case.overview')}
          </Typography>
          <MarkdownEditor content={overview} setContent={setOverview} height="200px" fontSize={14} />
        </Stack>
      </Stack>

      {entries.length > 0 ? (
        <>
          <Divider>
            <Typography variant="caption" color="textSecondary">
              {t('modal.cases.create_case.items_section')}
            </Typography>
          </Divider>
          <Stack spacing={1} overflow="auto" flex={1}>
            {entries.map((entry, i) => (
              <CaseRecordRow
                key={entry.record.howler.id}
                entry={entry}
                onTitleChange={val => updateEntry(i, 'title', val)}
                onPathChange={val => updateEntry(i, 'path', val)}
              />
            ))}
          </Stack>
        </>
      ) : (
        <div style={{ flex: 1 }} />
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

export default CreateCaseModal;
