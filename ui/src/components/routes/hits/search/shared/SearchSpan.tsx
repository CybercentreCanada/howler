import { AvTimer } from '@mui/icons-material';
import { Autocomplete, Stack, TextField, Typography } from '@mui/material';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import { ViewContext } from 'components/app/providers/ViewProvider';
import ChipPopper from 'components/elements/display/ChipPopper';
import dayjs from 'dayjs';
import type { FC } from 'react';
import { memo, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation, useSearchParams } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import { convertLuceneToDate } from 'utils/utils';
import CustomSpan from './CustomSpan';

const DATE_RANGES = [
  'date.range.1.day',
  'date.range.3.day',
  'date.range.1.week',
  'date.range.1.month',
  'date.range.all',
  'date.range.custom'
];

const SearchSpan: FC<{
  omitCustom?: boolean;
  size?: 'small' | 'medium';
}> = ({ omitCustom = false, size }) => {
  const { t } = useTranslation();
  const location = useLocation();
  const [params, setParams] = useSearchParams(); // Add this at the top of the component
  const views = useContextSelector(ParameterContext, ctx => ctx.views);
  const span = useContextSelector(ParameterContext, ctx => ctx.span);
  const setSpan = useContextSelector(ParameterContext, ctx => ctx.setSpan);

  const defaultStartDate = dayjs().subtract(2, 'days');
  const defaultEndDate = dayjs().subtract(1, 'day');

  const startDate = useContextSelector(ParameterContext, ctx =>
    ctx.startDate ? dayjs(ctx.startDate) : defaultStartDate
  );
  const endDate = useContextSelector(ParameterContext, ctx => (ctx.endDate ? dayjs(ctx.endDate) : defaultEndDate));
  const setCustomSpan = useContextSelector(ParameterContext, ctx => ctx.setCustomSpan); // Add this

  const getCurrentViews = useContextSelector(ViewContext, ctx => ctx.getCurrentViews);

  useEffect(() => {
    if (location.search.includes('span')) {
      return;
    }

    (async () => {
      const selectedViewSpan = (await getCurrentViews({ lazy: true })).find(view => view?.span)?.span;

      if (!selectedViewSpan) {
        return;
      }

      if (selectedViewSpan.includes(':')) {
        setSpan(convertLuceneToDate(selectedViewSpan));
      } else {
        setSpan(selectedViewSpan);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [getCurrentViews, views]);

  // TODO : AG : here rely the bug
  // I think its looking at the url or a variable and see something is already there thus custom
  // I'll try that in next update
  return (
    <ChipPopper
      icon={<AvTimer fontSize="small" />}
      label={
        <Typography variant="body2">
          {span !== 'date.range.custom'
            ? t(span)
            : `${startDate?.format('YYYY-MM-DD HH:mm') ?? '?'} ${t('to')} ${endDate?.format('YYYY-MM-DD HH:mm') ?? '?'}`}
        </Typography>
      }
      minWidth="225px"
      slotProps={{ chip: { size: 'small' } }}
    >
      <Stack spacing={1}>
        <Autocomplete
          fullWidth
          sx={{ minWidth: '200px', flex: 1 }}
          size={size ?? 'small'}
          value={span}
          options={omitCustom ? DATE_RANGES.slice(0, DATE_RANGES.length - 1) : DATE_RANGES}
          renderInput={_params => <TextField {..._params} label={t('hit.search.span')} />} // here ?
          getOptionLabel={option => t(option)}
          onChange={(_, value) => {
            if (!value) return;

            if (value !== 'date.range.custom') {
              // 1. Create a fresh copy of current params
              const newParams = new URLSearchParams(params);
              newParams.set('span', value);
              newParams.delete('start_date');
              newParams.delete('end_date');
              setParams(newParams);
            } else {
              // If they actually want custom, let the provider handle it
              setSpan(value);
            }
          }} // Got to find a way to clear the url
          disableClearable
        />

        <CustomSpan />
      </Stack>
    </ChipPopper>
  );
};

export default memo(SearchSpan);
