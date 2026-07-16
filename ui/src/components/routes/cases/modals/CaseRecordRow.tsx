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
import type { FolderOption, RecordEntry } from './types';

const CaseRecordRow: FC<{
  entry: RecordEntry;
  folderOptions?: FolderOption[];
  onNameChange: (name: string) => void;
  onParentChange: (parent: string | null) => void;
}> = ({ entry, folderOptions = [], onNameChange, onParentChange }) => {
  const { t } = useTranslation();
  const { record, parent, name } = entry;

  const selectedFolder = folderOptions.find(f => f.id === parent) ?? null;

  return (
    <Accordion variant="outlined" defaultExpanded sx={{ flexShrink: 0 }}>
      <AccordionSummary
        expandIcon={<KeyboardArrowDown />}
        sx={{ px: 1, minHeight: '48px !important', '& > *': { margin: '0 !important' } }}
      >
        <Stack direction="row" alignItems="center" spacing={1} width="100%">
          <Typography variant="body2" fontWeight={500} sx={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {isHit(record) ? record.howler.analytic : 'Event'}
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
          {folderOptions.length > 0 && (
            <Autocomplete
              disablePortal
              options={folderOptions}
              getOptionLabel={opt => opt.label}
              isOptionEqualToValue={(opt, val) => opt.id === val.id}
              value={selectedFolder}
              onChange={(_ev, newVal) => onParentChange(newVal?.id ?? null)}
              renderInput={params => (
                <TextField
                  {...params}
                  size="small"
                  placeholder={t('modal.cases.add_to_case.select_folder')}
                  fullWidth
                />
              )}
            />
          )}
          <TextField
            size="small"
            fullWidth
            placeholder={t('modal.cases.add_to_case.name')}
            value={name}
            onChange={ev => onNameChange(ev.target.value)}
          />
        </Stack>
      </AccordionDetails>
    </Accordion>
  );
};

export default CaseRecordRow;
