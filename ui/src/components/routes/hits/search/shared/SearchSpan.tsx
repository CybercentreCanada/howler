import { AvTimer } from '@mui/icons-material';
import { Autocomplete, Stack, TextField, Typography } from '@mui/material';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import { ViewContext } from 'components/app/providers/ViewProvider';
import ChipPopper from 'components/elements/display/ChipPopper';
import dayjs from 'dayjs';
import type { FC } from 'react';
import { memo, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';
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

  const span = useContextSelector(ParameterContext, ctx => ctx.span);
  const setSpan = useContextSelector(ParameterContext, ctx => ctx.setSpan);

  const startDate = useContextSelector(ParameterContext, ctx => (ctx.startDate ? dayjs(ctx.startDate) : null));
  const endDate = useContextSelector(ParameterContext, ctx => (ctx.endDate ? dayjs(ctx.endDate) : null));

  const getCurrentView = useContextSelector(ViewContext, ctx => ctx.getCurrentView);

  useEffect(() => {
    if (location.search.includes('span')) {
      return;
    }

    (async () => {
      const viewSpan = (await getCurrentView({ lazy: true }))?.span;

      if (!viewSpan) {
        return;
      }

      if (viewSpan.includes(':')) {
        setSpan(convertLuceneToDate(viewSpan));
      } else {
        setSpan(viewSpan);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [getCurrentView]);

  return (
    <ChipPopper
      icon={<AvTimer fontSize="small" />}
      label={
        <Typography variant="body2">
          {span !== 'date.range.custom'
            ? t(span)
            : `${startDate.format('YYYY-MM-DD HH:mm')} ${t('to')} ${endDate.format('YYYY-MM-DD HH:mm')}`}
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
          renderInput={_params => <TextField {..._params} label={t('hit.search.span')} />}
          getOptionLabel={option => t(option)}
          onChange={(_, value) => setSpan(value)}
          disableClearable
        />

        <CustomSpan />
      </Stack>
    </ChipPopper>
  );
};

export default memo(SearchSpan);
