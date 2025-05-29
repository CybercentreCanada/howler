import { Add, Check } from '@mui/icons-material';
import { Autocomplete, Chip, Divider, Grid, Popover, Stack, TextField } from '@mui/material';
import { FieldContext } from 'components/app/providers/FieldProvider';
import { HitSearchContext } from 'components/app/providers/HitSearchProvider';
import { TemplateContext } from 'components/app/providers/TemplateProvider';
import { sortBy, uniq } from 'lodash-es';
import { memo, useContext, useMemo, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useContextSelector } from 'use-context-selector';

const AddColumnModal: FC<{
  open: boolean;
  onClose: () => void;
  anchorEl: HTMLElement;
  addColumn: (key: string) => void;
  columns: string[];
}> = ({ open, onClose, anchorEl, addColumn, columns }) => {
  const { t } = useTranslation();
  const { hitFields } = useContext(FieldContext);

  const response = useContextSelector(HitSearchContext, ctx => ctx.response);

  const getMatchingTemplate = useContextSelector(TemplateContext, ctx => ctx.getMatchingTemplate);

  const options = useMemo(() => hitFields.map(field => field.key), [hitFields]);
  const suggestions = useMemo(
    () => uniq((response?.items ?? []).flatMap(_hit => getMatchingTemplate(_hit)?.keys ?? [])),
    [getMatchingTemplate, response?.items]
  );

  return (
    <Popover
      open={open}
      onClose={onClose}
      anchorEl={anchorEl}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
    >
      <Stack spacing={1} p={1} width="500px">
        <Autocomplete
          options={options}
          renderInput={params => <TextField fullWidth placeholder={t('hit.fields')} {...params} />}
        />
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
    </Popover>
  );
};

export default memo(AddColumnModal);
