import { OpenInNew, PlayArrowOutlined } from '@mui/icons-material';
import {
  Autocomplete,
  Card,
  Checkbox,
  Chip,
  CircularProgress,
  FormControlLabel,
  IconButton,
  ListItemText,
  Slider,
  Stack,
  TextField,
  Tooltip,
  Typography,
  useMediaQuery
} from '@mui/material';
import Popper, { type PopperProps } from '@mui/material/Popper';
import CustomButton from 'components/elements/addons/buttons/CustomButton';
import type { FC, KeyboardEventHandler } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { sanitizeMultilineLucene } from 'utils/stringUtils';

export const QUERY_TYPES = ['eql', 'lucene', 'yaml'] as const;
export type QueryLanguage = (typeof QUERY_TYPES)[number];

export const LUCENE_QUERY_OPTIONS = ['default', 'facet', 'groupby', 'explain'] as const;
export type LuceneQueryType = (typeof LUCENE_QUERY_OPTIONS)[number];

export const STEPS = [1, 5, 25, 50, 100, 250, 500, 1000, 2500, 10000];

const CustomPopper = (props: PopperProps) => {
  return <Popper {...props} style={{ width: 'fit-content' }} placement="bottom-start" />;
};

interface ExecuteQueryButtonProps {
  loading: boolean;
  searchDisabled: boolean;
  onExecute: () => void;
}

export const ExecuteQueryButton: FC<ExecuteQueryButtonProps> = ({ loading, searchDisabled, onExecute }) => {
  const { t } = useTranslation();
  const smallButtons = useMediaQuery('(max-width:1150px)');

  return smallButtons ? (
    <Tooltip title={t('route.actions.execute')}>
      <IconButton
        size="small"
        sx={{ alignSelf: 'start' }}
        color="success"
        onClick={onExecute}
        disabled={searchDisabled}
      >
        {loading ? (
          <CircularProgress size={18} color="success" />
        ) : (
          <PlayArrowOutlined color={searchDisabled ? 'disabled' : 'success'} />
        )}
      </IconButton>
    </Tooltip>
  ) : (
    <CustomButton
      size="small"
      variant="outlined"
      startIcon={
        loading ? (
          <CircularProgress size={18} color="success" />
        ) : (
          <PlayArrowOutlined
            color={searchDisabled ? 'disabled' : 'success'}
            sx={{ '& path': { stroke: 'currentcolor', strokeWidth: '1px' } }}
          />
        )
      }
      color="success"
      onClick={onExecute}
      disabled={searchDisabled}
    >
      {t('route.actions.execute')}
    </CustomButton>
  );
};

interface QueryLanguageSelectProps {
  value: QueryLanguage;
  onChange: (language: QueryLanguage) => void;
  compactLayout: boolean;
}

export const QueryLanguageSelect: FC<QueryLanguageSelectProps> = ({ value, onChange, compactLayout }) => {
  const { t } = useTranslation();

  return (
    <Autocomplete
      value={value}
      onChange={(__, nextValue) => onChange(nextValue as QueryLanguage)}
      options={QUERY_TYPES}
      getOptionLabel={option => t(`route.advanced.query.${option}`)}
      renderOption={(props, option) => (
        <ListItemText
          {...(props as any)}
          sx={{ flexDirection: 'column', alignItems: 'start !important' }}
          primary={t(`route.advanced.query.${option}`)}
          secondary={t(`route.advanced.query.${option}.description`)}
        />
      )}
      renderInput={params => (
        <TextField {...params} size="small" label={t('route.advanced.query.type')} sx={{ minWidth: '250px' }} />
      )}
      sx={[
        !compactLayout && {
          height: '100%',
          '& .MuiFormControl-root': { height: '100%', '& > div': { height: '100%' } }
        }
      ]}
      slotProps={{ paper: { sx: { minWidth: '600px' } } }}
    />
  );
};

interface RowsControlProps {
  value: number;
  onChange: (rows: number) => void;
}

export const RowsControl: FC<RowsControlProps> = ({ value, onChange }) => {
  const { t } = useTranslation();

  return (
    <Card variant="outlined" sx={{ flex: 1, maxWidth: '350px', minWidth: '210px' }}>
      <Stack spacing={0.5} sx={{ px: 1, alignItems: 'start' }}>
        <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>
          {t('route.advanced.rows')}: {STEPS[value]}
        </Typography>
        <Slider
          size="small"
          valueLabelDisplay="off"
          value={value}
          onChange={(_, nextValue) => onChange(nextValue as number)}
          min={0}
          max={9}
          step={1}
          marks
          track={false}
          sx={{ py: 0.5 }}
        />
      </Stack>
    </Card>
  );
};

interface LuceneQueryTypeSelectProps {
  value: LuceneQueryType;
  onChange: (queryType: LuceneQueryType) => void;
}

export const LuceneQueryTypeSelect: FC<LuceneQueryTypeSelectProps> = ({ value, onChange }) => {
  const { t } = useTranslation();

  return (
    <Autocomplete
      size="small"
      getOptionLabel={option => t(`route.advanced.query.type.${option}`)}
      options={LUCENE_QUERY_OPTIONS}
      value={value}
      onChange={(_, nextValue) => onChange(nextValue ?? 'default')}
      renderInput={params => (
        <TextField {...params} label={t('route.advanced.query.lucene.type')} sx={{ minWidth: '230px' }} />
      )}
      renderOption={(props, option) => (
        <ListItemText
          {...(props as any)}
          sx={{ flexDirection: 'column', alignItems: 'start !important' }}
          primary={t(`route.advanced.query.type.${option}`)}
          secondary={t(`route.advanced.query.type.${option}.description`)}
        />
      )}
    />
  );
};

interface GroupByFieldSelectProps {
  options: string[];
  value: string;
  onChange: (field: string) => void;
  onKeyDown?: KeyboardEventHandler<HTMLDivElement>;
}

export const GroupByFieldSelect: FC<GroupByFieldSelectProps> = ({ options, value, onChange, onKeyDown }) => {
  const { t } = useTranslation();

  return (
    <Autocomplete
      size="small"
      options={options}
      value={value}
      onChange={(__, nextValue) => onChange(nextValue ?? '')}
      renderInput={params => <TextField {...params} label={t('route.advanced.pivot.field')} />}
      sx={{ minWidth: '200px', '& label': { zIndex: 1200 } }}
      onKeyDown={onKeyDown}
      PopperComponent={CustomPopper}
    />
  );
};

interface FieldsControlProps {
  allFields: boolean;
  onAllFieldsChange: (checked: boolean) => void;
  queryType: LuceneQueryType;
  fieldOptions: string[];
  fields: string[];
  onFieldsChange: (fields: string[]) => void;
  onKeyDown?: KeyboardEventHandler<HTMLDivElement>;
}

export const FieldsControl: FC<FieldsControlProps> = ({
  allFields,
  onAllFieldsChange,
  queryType,
  fieldOptions,
  fields,
  onFieldsChange,
  onKeyDown
}) => {
  const { t } = useTranslation();

  return allFields && queryType !== 'facet' ? (
    <FormControlLabel
      control={<Checkbox size="small" checked={allFields} onChange={(__, checked) => onAllFieldsChange(checked)} />}
      label={t('route.advanced.fields.all')}
      sx={{ '& > span': { color: 'text.secondary' }, alignSelf: 'start' }}
    />
  ) : (
    <Autocomplete
      fullWidth
      renderTags={values =>
        values.length <= 3 ? (
          <Stack direction="row" spacing={0.5}>
            {values.map(_value => (
              <Chip key={_value} label={_value} />
            ))}
          </Stack>
        ) : (
          <Tooltip
            title={
              <Stack spacing={1}>
                {values.map(_value => (
                  <span key={_value}>{_value}</span>
                ))}
              </Stack>
            }
          >
            <Chip label={values.length} />
          </Tooltip>
        )
      }
      multiple
      size="small"
      options={fieldOptions}
      value={fields}
      onChange={(__, values) => (values.length > 0 ? onFieldsChange(values) : onAllFieldsChange(true))}
      renderInput={params => <TextField {...params} label={t('route.advanced.fields')} />}
      sx={{ maxWidth: '500px', width: '20vw', minWidth: '200px', '& label': { zIndex: 1200 } }}
      onKeyDown={onKeyDown}
      slots={{ popper: CustomPopper }}
    />
  );
};

interface OpenInSearchButtonProps {
  query: string;
  hasResponse: boolean;
}

export const OpenInSearchButton: FC<OpenInSearchButtonProps> = ({ query, hasResponse }) => {
  const { t } = useTranslation();
  const smallButtons = useMediaQuery('(max-width:1150px)');
  const to = `/hits?query=${sanitizeMultilineLucene(query).replaceAll('\n', ' ').trim()}`;

  return smallButtons ? (
    <Tooltip title={t('route.advanced.open')}>
      <IconButton color="primary" sx={{ alignSelf: 'center' }} component={Link} disabled={!hasResponse} to={to}>
        <OpenInNew fontSize="small" />
      </IconButton>
    </Tooltip>
  ) : (
    <CustomButton
      size="small"
      variant="outlined"
      startIcon={<OpenInNew />}
      component={Link}
      disabled={!hasResponse}
      // TuiButton doesn't accept this prop even through the underlying component does, so this needs a cast.
      {...({ to } as any)}
    >
      {t('route.advanced.open')}
    </CustomButton>
  );
};
