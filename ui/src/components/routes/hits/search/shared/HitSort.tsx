import { Sort } from '@mui/icons-material';
import { Autocomplete, Stack, TextField } from '@mui/material';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import { ViewContext } from 'components/app/providers/ViewProvider';
import ChipPopper from 'components/elements/display/ChipPopper';
import type { FC } from 'react';
import { memo, useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import CustomSort from './CustomSort';

const CUSTOM = '__custom__';

const ACCEPTED_SORTS = [
  'event.created',
  'howler.assessment',
  'howler.escalation',
  'howler.analytic',
  'howler.detection',
  'event.provider',
  'organization.name',
  'howler.score',
  CUSTOM
];

const HitSort: FC<{ size?: 'small' | 'medium' }> = ({ size = 'small' }) => {
  const { t } = useTranslation();
  const location = useLocation();
  const getCurrentViews = useContextSelector(ViewContext, ctx => ctx.getCurrentViews);

  const views = useContextSelector(ParameterContext, ctx => ctx.views);
  const savedSort = useContextSelector(ParameterContext, ctx => ctx.sort);
  const setSavedSort = useContextSelector(ParameterContext, ctx => ctx.setSort);

  const sortEntries = useMemo(() => savedSort.split(',').filter(part => !!part), [savedSort]);

  /**
   * The currently selected field when not using custom sorting
   */
  const field = useMemo(() => (sortEntries.length === 1 ? sortEntries[0].split(' ')[0] : null), [sortEntries]);

  /**
   * The currently selected sorter when not using custom sorting
   */
  const sort = useMemo(
    () => (sortEntries.length === 1 ? sortEntries[0].split(' ')[1] : null) as 'asc' | 'desc',
    [sortEntries]
  );

  /**
   * Should the custom sorter be shown? Defaults to true if there's more than one sort field, or we're sorting on a field not supported by the default dropdown
   */
  const [showCustomSort, setShowCustomSort] = useState(
    sortEntries.length > 1 || (sortEntries.length > 0 && !ACCEPTED_SORTS.includes(sortEntries[0]?.split(' ')[0]))
  );

  /**
   * This handles changing the sort if the basic sorter is used, OR enables the custom sorting.
   */
  const handleChange = useCallback(
    (value: string) => {
      if (value === CUSTOM) {
        setShowCustomSort(true);
      } else {
        setSavedSort(`${value} ${sort}`);
      }
    },
    [setSavedSort, sort]
  );

  useEffect(() => {
    if (location.search.includes('sort')) {
      return;
    }

    (async () => {
      const selectedViewSort = (await getCurrentViews({ lazy: true })).find(view => view?.sort)?.sort;

      if (selectedViewSort && !location.search.includes('sort')) {
        setSavedSort(selectedViewSort);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [getCurrentViews, views]);

  return (
    <ChipPopper icon={<Sort fontSize="small" />} label={savedSort} slotProps={{ chip: { size: 'small' } }}>
      {!showCustomSort ? (
        <Stack
          spacing={1}
          onClick={e => {
            e.stopPropagation();
            e.preventDefault();
          }}
        >
          <Autocomplete
            fullWidth
            sx={{ minWidth: '275px' }}
            size={size}
            value={field}
            options={ACCEPTED_SORTS}
            getOptionLabel={option => (option === CUSTOM ? t('hit.search.custom') : option)}
            isOptionEqualToValue={(option, value) => option === value || (!value && option === ACCEPTED_SORTS[0])}
            renderInput={_params => <TextField {..._params} label={t('hit.search.sort.fields')} />}
            onChange={(_, value) => handleChange(value)}
          />
          <Autocomplete
            fullWidth
            size={size}
            sx={{ minWidth: '150px' }}
            value={sort}
            onChange={(_e, value) => {
              setSavedSort(`${field} ${value as 'asc' | 'desc'}`);
            }}
            options={['asc', 'desc']}
            getOptionLabel={option => t(option)}
            renderInput={_params => <TextField {..._params} />}
          />
        </Stack>
      ) : (
        <CustomSort />
      )}
    </ChipPopper>
  );
};

export default memo(HitSort);
