import { FilterList } from '@mui/icons-material';
import { List, ListItemButton, ListItemText } from '@mui/material';
import { ParameterContext, type SearchIndex } from 'components/app/providers/ParameterProvider';
import ChipPopper from 'components/elements/display/ChipPopper';
import { memo, useCallback, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useContextSelector } from 'use-context-selector';

const FILTER_OPTIONS: { label: string; value: SearchIndex }[] = [
  { label: 'hit.search.filter.hit', value: 'hit' },
  { label: 'hit.search.filter.observable', value: 'observable' }
];

const SearchFilter: FC = () => {
  const { t } = useTranslation();
  const searchIndex = useContextSelector(ParameterContext, ctx => ctx.searchIndex);
  const setSearchIndex = useContextSelector(ParameterContext, ctx => ctx.setSearchIndex);

  const handleSelect = useCallback(
    (value: SearchIndex) => {
      setSearchIndex(value);
    },
    [setSearchIndex]
  );

  const selectedOption = FILTER_OPTIONS.find(opt => opt.value === searchIndex) ?? FILTER_OPTIONS[0];

  return (
    <ChipPopper
      icon={<FilterList fontSize="small" />}
      label={t(selectedOption.label)}
      minWidth="225px"
      slotProps={{ chip: { size: 'small' } }}
      closeOnClick
    >
      <List disablePadding>
        {FILTER_OPTIONS.map(option => (
          <ListItemButton
            key={option.value}
            selected={option.value === searchIndex}
            onClick={() => handleSelect(option.value)}
          >
            <ListItemText primary={t(option.label)} />
          </ListItemButton>
        ))}
      </List>
    </ChipPopper>
  );
};

export default memo(SearchFilter);
