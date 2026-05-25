import { Stack } from '@mui/material';
import { LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import dayjs from 'dayjs';
import { memo, useEffect, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useContextSelector } from 'use-context-selector';

const CustomSpan: FC<{}> = () => {
  const { t } = useTranslation();

  const span = useContextSelector(ParameterContext, ctx => ctx.span);
  const setCustomSpan = useContextSelector(ParameterContext, ctx => ctx.setCustomSpan);
  const startDate = useContextSelector(ParameterContext, ctx => (ctx.startDate ? dayjs(ctx.startDate) : null));
  const endDate = useContextSelector(ParameterContext, ctx => (ctx.endDate ? dayjs(ctx.endDate) : null));

  useEffect(() => {
    if (span?.endsWith('custom') && (!startDate || !endDate)) {
      const _startDate = startDate ?? dayjs().subtract(2, 'day');
      const _endDate = endDate ?? dayjs().subtract(1, 'day');

      setCustomSpan(dayjs.min(_startDate, _endDate).toISOString(), dayjs.max(_startDate, _endDate).toISOString());
    }
  }, [endDate, setCustomSpan, span, startDate]);

  return span?.endsWith('custom') ? (
    <LocalizationProvider dateAdapter={AdapterDayjs}>
      <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
        <DateTimePicker
          sx={{ minWidth: '175px', flexGrow: 1, marginTop: 1 }}
          slotProps={{ textField: { size: 'small' } }}
          label={t('date.select.start')}
          value={startDate ? dayjs(startDate) : dayjs().subtract(1, 'days')}
          maxDateTime={endDate}
          onChange={(newStartDate: dayjs.Dayjs) => setCustomSpan(newStartDate.toISOString(), endDate.toISOString())}
          ampm={false}
          disableFuture
        />

        <DateTimePicker
          sx={{ minWidth: '175px', flexGrow: 1, marginTop: 1 }}
          slotProps={{ textField: { size: 'small' } }}
          label={t('date.select.end')}
          value={endDate}
          minDateTime={startDate}
          onChange={(newEndDate: dayjs.Dayjs) => setCustomSpan(startDate.toISOString(), newEndDate.toISOString())}
          ampm={false}
          disableFuture
        />
      </Stack>
    </LocalizationProvider>
  ) : null;
};

export default memo(CustomSpan);
