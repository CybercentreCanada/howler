import { ArrowDownward, ArrowUpward, Cancel } from '@mui/icons-material';
import { Autocomplete, Chip, Grid, MenuItem, Select, Stack, TextField } from '@mui/material';
import { FieldContext } from 'components/app/providers/FieldProvider';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import { uniqBy } from 'lodash-es';
import type { FC } from 'react';
import { memo, useContext, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useContextSelector } from 'use-context-selector';

const CustomSort: FC = () => {
  const { t } = useTranslation();
  const [field, setField] = useState('');
  const [sort, setSort] = useState<'asc' | 'desc' | ''>('');
  const { hitFields, getHitFields } = useContext(FieldContext);

  const sortEntries = useContextSelector(ParameterContext, ctx => ctx.sort?.split(','));
  const setSavedSort = useContextSelector(ParameterContext, ctx => ctx.setSort);

  const sortFields = useMemo(
    () => sortEntries.map(entry => entry.split(' ').slice(0, 2) as [string, string]),
    [sortEntries]
  );

  useEffect(() => {
    getHitFields();
  }, [getHitFields]);

  useEffect(() => {
    if (!sort) {
      setSort('desc');
    }
  }, [sort]);

  useEffect(() => {
    if (!field) {
      return;
    }

    setSavedSort(uniqBy([...sortEntries, `${field} ${sort}`], entry => entry.replace(/ .+/, '')).join(','));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [field]);

  return (
    <Stack spacing={1} maxWidth="450px">
      <Stack direction="row" spacing={1}>
        <Autocomplete
          fullWidth
          sx={{ minWidth: '225px' }}
          size="small"
          value={field}
          options={hitFields.map(_field => _field.key)}
          getOptionDisabled={option => sortEntries.map(entry => entry.replace(/ .+/, '')).includes(option)}
          renderInput={_params => <TextField {..._params} label={t('hit.search.sort.fields')} />}
          onChange={(_, value) => setField(value)}
          disableClearable
        />
        <Select
          size="small"
          sx={{ minWidth: '150px' }}
          value={sort}
          onChange={e => setSort(e.target.value as 'asc' | 'desc')}
        >
          <MenuItem value="asc">{t('asc')}</MenuItem>
          <MenuItem value="desc">{t('desc')}</MenuItem>
        </Select>
      </Stack>
      <Grid container spacing={1} sx={theme => ({ marginLeft: `${theme.spacing(-1)} !important` })}>
        {sortFields.map(([key, direction]) => (
          <Grid item key={key}>
            <Chip
              variant="outlined"
              label={key}
              icon={direction === 'asc' ? <ArrowUpward /> : <ArrowDownward />}
              deleteIcon={<Cancel />}
              onClick={() =>
                setSavedSort(
                  sortEntries
                    .map(entry =>
                      entry?.replace(`${key} ${direction}`, `${key} ${direction === 'asc' ? 'desc' : 'asc'}`)
                    )
                    .join(',')
                )
              }
              onDelete={() => setSavedSort(sortEntries.filter(entry => entry && entry.split(' ')[0] != key).join(','))}
            />
          </Grid>
        ))}
      </Grid>
    </Stack>
  );
};

export default memo(CustomSort);
