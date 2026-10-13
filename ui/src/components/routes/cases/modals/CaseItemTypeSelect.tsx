import { Autocomplete, TextField } from '@mui/material';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

export const CASE_ITEM_TYPES = [
  { value: 'reference', labelKey: 'modal.cases.add_item.type.link' },
  { value: 'markdown', labelKey: 'modal.cases.add_item.type.markdown' }
] as const;

export type CaseItemType = (typeof CASE_ITEM_TYPES)[number];

interface CaseItemTypeSelectProps {
  value: CaseItemType;
  onChange: (itemType: CaseItemType) => void;
}

const CaseItemTypeSelect: FC<CaseItemTypeSelectProps> = ({ value, onChange }) => {
  const { t } = useTranslation();

  return (
    <Autocomplete
      value={value}
      onChange={(_, option) => {
        if (option) {
          onChange(option);
        }
      }}
      options={CASE_ITEM_TYPES}
      getOptionLabel={option => t(option.labelKey)}
      isOptionEqualToValue={(option, choice) => option.value === choice.value}
      disablePortal
      disableClearable
      renderInput={params => (
        <TextField {...params} size="small" label={t('modal.cases.add_item.type')} sx={{ minWidth: '175px' }} />
      )}
    />
  );
};

export default CaseItemTypeSelect;
