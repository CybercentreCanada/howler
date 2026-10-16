import { Autocomplete, TextField } from '@mui/material';
import CaseCard from 'components/elements/case/CaseCard';
import type { Case } from 'models/entities/generated/Case';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

interface CaseSelectorProps {
  options: Case[];
  value: Case | null;
  onChange: (selectedCase: Case | null) => void;
}

const CaseSelector: FC<CaseSelectorProps> = ({ options, value, onChange }) => {
  const { t } = useTranslation();

  return (
    <Autocomplete<Case>
      options={options}
      getOptionLabel={option => option.title ?? option.case_id ?? ''}
      isOptionEqualToValue={(option, selected) => option.case_id === selected.case_id}
      value={value}
      disablePortal
      onChange={(_ev, nextCase) => onChange(nextCase)}
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
  );
};

export default CaseSelector;
