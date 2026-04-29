import { KeyboardArrowDown } from '@mui/icons-material';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Autocomplete,
  Chip,
  Stack,
  TextField,
  Typography
} from '@mui/material';
import EscalationChip from 'components/elements/hit/elements/EscalationChip';
import { HitLayout } from 'components/elements/hit/HitLayout';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';
import { isHit } from 'utils/typeUtils';
import type { RecordEntry } from './types';

const CaseRecordRow: FC<{
  entry: RecordEntry;
  folderOptions?: string[];
  onTitleChange: (title: string) => void;
  onPathChange: (path: string) => void;
}> = ({ entry, folderOptions = [], onTitleChange, onPathChange }) => {
  const { t } = useTranslation();
  const { record, path, title } = entry;
  const fullPath = path ? `${path}/${title}` : title;
  const pathError = path.startsWith('/') || path.endsWith('/');

  return (
    <Accordion variant="outlined" defaultExpanded sx={{ flexShrink: 0 }}>
      <AccordionSummary
        expandIcon={<KeyboardArrowDown />}
        sx={{ px: 1, minHeight: '48px !important', '& > *': { margin: '0 !important' } }}
      >
        <Stack direction="row" alignItems="center" spacing={1} width="100%">
          <Typography variant="body2" fontWeight={500} sx={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {isHit(record) ? record.howler.analytic : 'Observable'}
          </Typography>
          {isHit(record) && <EscalationChip hit={record} layout={HitLayout.DENSE} />}
          {isHit(record) && <Chip label={record.howler.status} size="small" color="primary" sx={{ flexShrink: 0 }} />}
          <Typography variant="caption" color="textSecondary" sx={{ flexShrink: 0 }}>
            {record.howler.id}
          </Typography>
        </Stack>
      </AccordionSummary>
      <AccordionDetails>
        <Stack spacing={1}>
          <Autocomplete
            freeSolo
            disablePortal
            options={folderOptions}
            value={path}
            onInputChange={(_ev, newVal) => onPathChange(newVal)}
            renderInput={params => (
              <TextField
                {...params}
                size="small"
                placeholder={t('modal.cases.add_to_case.select_path')}
                fullWidth
                error={pathError}
                helperText={pathError ? t('modal.cases.add_to_case.path_invalid') : undefined}
              />
            )}
          />
          <TextField
            size="small"
            fullWidth
            placeholder={t('modal.cases.add_to_case.title')}
            value={title}
            onChange={ev => onTitleChange(ev.target.value)}
          />
          {title && (
            <Typography variant="caption" color="textSecondary">
              {t('modal.cases.add_to_case.full_path', { path: fullPath })}
            </Typography>
          )}
        </Stack>
      </AccordionDetails>
    </Accordion>
  );
};

export default CaseRecordRow;
