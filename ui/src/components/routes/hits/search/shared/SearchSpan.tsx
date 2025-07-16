import { Autocomplete, TextField } from '@mui/material';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import { ViewContext } from 'components/app/providers/ViewProvider';
import type { FC } from 'react';
import { memo, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import { convertLuceneToDate } from 'utils/utils';

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

  const getCurrentView = useContextSelector(ViewContext, ctx => ctx.getCurrentView);

  useEffect(() => {
    if (location.search.includes('span')) {
      return;
    }

    (async () => {
      const viewSpan = (await getCurrentView(true))?.span;

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
  );
};

export default memo(SearchSpan);
