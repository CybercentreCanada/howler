import { FilterList } from '@mui/icons-material';
import type { UseAutocompleteProps } from '@mui/material';
import { Autocomplete, Stack, TextField, Typography } from '@mui/material';
import api from 'api';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import ChipPopper from 'components/elements/display/ChipPopper';
import type { FC } from 'react';
import { memo, useCallback, useContext, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useContextSelector } from 'use-context-selector';
import { sanitizeLuceneQuery } from 'utils/stringUtils';

const ACCEPTED_LOOKUPS = [
  'howler.assessment',
  'howler.escalation',
  'howler.analytic',
  'howler.detection',
  'event.provider',
  'organization.name'
];

const HitFilter: FC<{ size?: 'small' | 'medium' }> = ({ size }) => {
  const { t } = useTranslation();
  const { config } = useContext(ApiConfigContext);

  const savedFilter = useContextSelector(ParameterContext, ctx => ctx.filter);
  const setSavedFilter = useContextSelector(ParameterContext, ctx => ctx.setFilter);

  const [category, setCategory] = useState(ACCEPTED_LOOKUPS[0]);
  const [filter, setFilter] = useState('');

  const [customLookups, setCustomLookups] = useState<string[]>([]);

  useEffect(() => {
    if (savedFilter) {
      const [_category, _filter] = (savedFilter || ':').split(':');

      if (_category) {
        setCategory(_category);
      }

      if (_filter) {
        setFilter(_filter);
      }

      if (_category && _filter) {
        setSavedFilter(`${_category}:${_filter}`);
      }
    }
  }, [setSavedFilter, savedFilter]);

  const onCategoryChange: UseAutocompleteProps<string, false, false, false>['onChange'] = useCallback(
    async (_, _category) => {
      setCategory(_category);
      setFilter('');

      setSavedFilter(null);

      if (!config.lookups[_category]) {
        const facets = await api.search.facet.hit.post({ query: 'howler.id:*', fields: [_category] });

        setCustomLookups(Object.keys(facets[_category]));
      } else {
        setCustomLookups([]);
      }
    },
    [config.lookups, setSavedFilter]
  );

  const onValueChange: UseAutocompleteProps<string, false, false, false>['onChange'] = useCallback(
    (_, value) => {
      setFilter(value);
      if (value) {
        const newFilter = `${category}:"${sanitizeLuceneQuery(value)}"`;

        setSavedFilter(newFilter);
      } else {
        setSavedFilter(null);
      }
    },
    [category, setSavedFilter]
  );

  const filterValue = filter?.replaceAll('"', '').replaceAll('\\-', '-') || '';

  return (
    <ChipPopper
      icon={<FilterList fontSize="small" />}
      label={category && filterValue && <Typography variant="body2">{`${category}:${filterValue}`}</Typography>}
      minWidth="225px"
    >
      <Stack spacing={1} sx={{ minWidth: '225px' }}>
        <Autocomplete
          fullWidth
          size={size ?? 'small'}
          value={category}
          options={ACCEPTED_LOOKUPS}
          renderInput={_params => <TextField {..._params} label={t('hit.search.filter.fields')} />}
          onChange={onCategoryChange}
        />
        <Autocomplete
          fullWidth
          freeSolo
          disabled={!category}
          size={size ?? 'small'}
          value={filter?.replaceAll('"', '').replaceAll('\\-', '-') || ''}
          options={config.lookups[category] ? config.lookups[category] : customLookups}
          renderInput={_params => <TextField {..._params} label={t('hit.search.filter.values')} />}
          getOptionLabel={option => t(option)}
          onChange={onValueChange}
        />
      </Stack>
    </ChipPopper>
  );
};

export default memo(HitFilter);
