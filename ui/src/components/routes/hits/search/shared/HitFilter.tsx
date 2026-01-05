import { FilterList } from '@mui/icons-material';
import type { UseAutocompleteProps } from '@mui/material';
import { Autocomplete, Stack, TextField, Typography } from '@mui/material';
import api from 'api';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import ChipPopper from 'components/elements/display/ChipPopper';
import useMyApi from 'components/hooks/useMyApi';
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

const HitFilter: FC<{ size?: 'small' | 'medium'; id: number; value: string }> = ({ size, id, value }) => {
  const { t } = useTranslation();
  const { config } = useContext(ApiConfigContext);
  const { dispatchApi } = useMyApi();

  const setSavedFilter = useContextSelector(ParameterContext, ctx => ctx.setFilter);
  const removeSavedFilter = useContextSelector(ParameterContext, ctx => ctx.removeFilter);

  const [category, setCategory] = useState(value?.split(':')[0] ?? ACCEPTED_LOOKUPS[0]);
  const [filter, setFilter] = useState(value?.split(':')[1] ?? null);
  const [loading, setLoading] = useState(false);

  const [customLookups, setCustomLookups] = useState<string[]>([]);

  useEffect(() => {
    if (value) {
      const [_category, _filter] = (value || ':').split(':');

      if (_category) {
        setCategory(_category);
      }

      if (_filter && _filter !== '*') {
        setFilter(_filter);
      }

      if (_category && _filter) {
        setSavedFilter(id, `${_category}:${_filter}`);
      }
    }
  }, [id, setSavedFilter, value]);

  const onCategoryChange: UseAutocompleteProps<string, false, false, false>['onChange'] = useCallback(
    async (_, _category) => {
      setCategory(_category);
      setFilter(null);

      if (!config.lookups[_category]) {
        setLoading(true);

        const facets = await dispatchApi(
          api.search.facet.hit.post({ query: 'howler.id:*', fields: [_category], rows: 100 }),
          {
            throwError: false
          }
        );

        setCustomLookups(Object.keys((facets ?? {})[_category]));
        setLoading(false);
      } else {
        setCustomLookups([]);
      }
    },
    [config.lookups, setSavedFilter]
  );

  const onValueChange: UseAutocompleteProps<string, false, false, false>['onChange'] = useCallback(
    (_, newValue) => {
      setFilter(newValue);

      if (newValue && newValue !== '*') {
        setSavedFilter(id, `${category}:"${sanitizeLuceneQuery(newValue)}"`);
      } else {
        setSavedFilter(id, `${category}:*`);
      }
    },
    [category, setSavedFilter]
  );

  const filterValue = filter?.replaceAll('"', '').replaceAll('\\-', '-') || '';

  return (
    <ChipPopper
      icon={<FilterList fontSize="small" />}
      label={category && <Typography variant="body2">{`${category}:${filterValue || '*'}`}</Typography>}
      minWidth="250px"
      onDelete={() => removeSavedFilter(value)}
      slotProps={{ chip: { size: 'small' } }}
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
          loading={loading}
          size={size ?? 'small'}
          value={filter?.replaceAll('"', '').replaceAll('\\-', '-') || ''}
          options={[...(config.lookups[category] ? config.lookups[category] : customLookups), '*']}
          renderInput={_params => <TextField {..._params} label={t('hit.search.filter.values')} />}
          getOptionLabel={option => t(option)}
          onChange={onValueChange}
        />
      </Stack>
    </ChipPopper>
  );
};

export default memo(HitFilter);
