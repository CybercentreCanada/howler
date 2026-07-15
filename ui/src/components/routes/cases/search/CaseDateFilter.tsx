import { AvTimer } from '@mui/icons-material';
import { Autocomplete, Stack, TextField, Typography } from '@mui/material';
import { LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import ChipPopper from 'components/elements/display/ChipPopper';
import type { Dayjs } from 'dayjs';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';
import { DATE_RANGES } from 'utils/constants';

export type DateRangeOption = (typeof DATE_RANGES)[number];

const CaseDateFilter: FC<{
  dateRange: DateRangeOption;
  onChange: (v: DateRangeOption) => void;
  customStart: Dayjs;
  customEnd: Dayjs;
  onCustomStartChange: (v: Dayjs) => void;
  onCustomEndChange: (v: Dayjs) => void;
}> = ({ dateRange, onChange, customStart, customEnd, onCustomStartChange, onCustomEndChange }) => {
  const { t } = useTranslation();

  return (
    <ChipPopper
      icon={<AvTimer fontSize="small" />}
      label={
        <Typography variant="body2">
          {dateRange === 'date.range.all'
            ? t('route.cases.filter.date')
            : dateRange === 'date.range.custom'
              ? `${customStart.format('YYYY-MM-DD')} ${t('to')} ${customEnd.format('YYYY-MM-DD')}`
              : t(dateRange)}
        </Typography>
      }
      minWidth="225px"
      slotProps={{ chip: { size: 'small', color: dateRange !== 'date.range.all' ? 'primary' : 'default' } }}
    >
      <Stack spacing={1}>
        <Autocomplete
          size="small"
          value={dateRange}
          options={[...DATE_RANGES]}
          getOptionLabel={o => t(o)}
          disableClearable
          onChange={(_, nv) => onChange(nv as DateRangeOption)}
          renderInput={params => <TextField {...params} label={t('route.cases.filter.date')} />}
        />
        {dateRange === 'date.range.custom' && (
          <LocalizationProvider dateAdapter={AdapterDayjs}>
            <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
              <DateTimePicker
                sx={{ minWidth: '175px', flexGrow: 1 }}
                slotProps={{ textField: { size: 'small' } }}
                label={t('date.select.start')}
                value={customStart}
                maxDate={customEnd}
                onChange={nv => {
                  if (nv) {
                    onCustomStartChange(nv);
                  }
                }}
                ampm={false}
                disableFuture
              />
              <DateTimePicker
                sx={{ minWidth: '175px', flexGrow: 1 }}
                slotProps={{ textField: { size: 'small' } }}
                label={t('date.select.end')}
                value={customEnd}
                minDate={customStart}
                onChange={nv => {
                  if (nv) {
                    onCustomEndChange(nv);
                  }
                }}
                ampm={false}
                disableFuture
              />
            </Stack>
          </LocalizationProvider>
        )}
      </Stack>
    </ChipPopper>
  );
};

export default CaseDateFilter;
