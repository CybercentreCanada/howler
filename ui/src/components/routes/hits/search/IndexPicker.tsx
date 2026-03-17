import { FilterList } from '@mui/icons-material';
import { Autocomplete, TextField } from '@mui/material';
import { ParameterContext, type SearchIndex } from 'components/app/providers/ParameterProvider';
import ChipPopper from 'components/elements/display/ChipPopper';
import { memo, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useContextSelector } from 'use-context-selector';

const FILTER_OPTIONS: { label: string; value: SearchIndex }[] = [
  { label: 'hit.search.filter.hit', value: 'hit' },
  { label: 'hit.search.filter.observable', value: 'observable' }
];

const IndexPicker: FC = () => {
  const { t } = useTranslation();
  const indexes = useContextSelector(ParameterContext, ctx => ctx.indexes);
  const setIndexes = useContextSelector(ParameterContext, ctx => ctx.setIndexes);

  const selectedOptions = FILTER_OPTIONS.filter(opt => indexes.includes(opt.value));

  return (
    <ChipPopper
      icon={<FilterList fontSize="small" />}
      label={selectedOptions.map(opt => t(opt.label)).join(', ')}
      minWidth="225px"
      slotProps={{ chip: { size: 'small' } }}
    >
      <Autocomplete
        size="small"
        multiple
        options={FILTER_OPTIONS}
        value={selectedOptions}
        onChange={(_ev, values) => values.length > 0 && setIndexes(values.map(val => val.value))}
        isOptionEqualToValue={(opt, val) => opt.value === val.value}
        getOptionLabel={opt => t(opt.label)}
        renderInput={params => <TextField {...params} />}
      />
    </ChipPopper>
  );
};

export default memo(IndexPicker);
