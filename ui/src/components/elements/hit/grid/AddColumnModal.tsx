import { Add, Check, Settings, TableChart } from '@mui/icons-material';
import { Autocomplete, Chip, Divider, Grid, IconButton, Stack, TextField } from '@mui/material';
import useMatchers from 'components/app/hooks/useMatchers';
import { FieldContext } from 'components/app/providers/FieldProvider';
import { RecordSearchContext } from 'components/app/providers/RecordSearchProvider';
import ChipPopper from 'components/elements/display/ChipPopper';
import { sortBy, uniq } from 'lodash-es';
import { memo, useContext, useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useContextSelector } from 'use-context-selector';
import { isHit } from 'utils/typeUtils';

const AddColumnModal: FC<{
  addColumn: (key: string) => void;
  columns: string[];
}> = ({ addColumn, columns }) => {
  const { t } = useTranslation();
  const { hitFields } = useContext(FieldContext);
  const response = useContextSelector(RecordSearchContext, ctx => ctx.response);
  const { getMatchingTemplate } = useMatchers();

  const [columnToAdd, setColumnToAdd] = useState<string>(null);

  const options = useMemo(() => hitFields.map(field => field.key), [hitFields]);
  const [suggestions, setSuggestions] = useState<string[]>([]);

  useEffect(() => {
    (async () => {
      setSuggestions(
        uniq(
          (
            await Promise.all(
              (response?.items ?? []).filter(isHit).map(async _hit => (await getMatchingTemplate(_hit))?.keys ?? [])
            )
          ).flat()
        )
      );
    })();
  }, [getMatchingTemplate, response?.items]);

  return (
    <ChipPopper icon={<TableChart />} deleteIcon={<Settings />} toggleOnDelete slotProps={{ chip: { size: 'small' } }}>
      <Stack spacing={1} p={1} width="500px">
        <Stack direction="row" spacing={1}>
          <Autocomplete
            sx={{ flex: 1 }}
            size="small"
            options={options}
            value={columnToAdd}
            renderInput={params => <TextField fullWidth placeholder={t('hit.fields')} {...params} />}
            onChange={(_ev, value) => setColumnToAdd(value)}
          />
          <IconButton
            disabled={!columnToAdd}
            onClick={() => {
              addColumn(columnToAdd);
              setColumnToAdd(null);
            }}
          >
            <Add />
          </IconButton>
        </Stack>
        <Divider orientation="horizontal" />
        <Grid container spacing={1}>
          {sortBy(
            suggestions.map(key => ({ key, used: columns.includes(key) })),
            'used'
          ).map(({ key, used }) => {
            return (
              <Grid item key={key}>
                <Chip
                  size="small"
                  variant="outlined"
                  color={used ? 'success' : 'default'}
                  label={key}
                  icon={used ? <Check /> : <Add />}
                  onClick={() => addColumn(key)}
                  disabled={used}
                />
              </Grid>
            );
          })}
        </Grid>
      </Stack>
    </ChipPopper>
  );
};

export default memo(AddColumnModal);
