import { AddCircleOutline, FilterList, RemoveCircleOutline } from '@mui/icons-material';
import type { UseAutocompleteProps } from '@mui/material';
import {
  Autocomplete,
  Checkbox,
  createFilterOptions,
  FormControlLabel,
  Stack,
  TextField,
  Tooltip,
  Typography
} from '@mui/material';
import api from 'api';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { FieldContext } from 'components/app/providers/FieldProvider';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import ChipPopper from 'components/elements/display/ChipPopper';
import useMyApi from 'components/hooks/useMyApi';
import { isEmpty, isNil, uniq } from 'lodash-es';
import type { APILookups } from 'models/entities/generated/ApiType';
import type { FC } from 'react';
import { memo, useCallback, useContext, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useContextSelector } from 'use-context-selector';
import { parseQuotedValues, sanitizeLuceneQuery } from 'utils/stringUtils';

const ACCEPTED_LOOKUPS = [
  'howler.assessment',
  'howler.escalation',
  'howler.analytic',
  'howler.detection',
  'event.provider',
  'organization.name'
] as const;

const DEFAULT_FILTER_FIELDS = [
  'howler.assessment',
  'howler.escalation',
  'howler.analytic',
  'howler.detection',
  'event.provider'
];

type AcceptedLookup = (typeof ACCEPTED_LOOKUPS)[number];

type ApiAcceptedLookup = Extract<AcceptedLookup, keyof APILookups>;

interface ParsedFilter {
  raw: string;
  category: AcceptedLookup | null;
  rawClause: string;
  values: string[];
  negated: boolean;
  editable: boolean;
  wildcard: boolean;
}

const parseFilter = (value: string): ParsedFilter => {
  const negated = value.startsWith('-');
  const positiveValue = negated ? value.slice(1) : value;
  const separator = positiveValue.indexOf(':');
  const category = separator > 0 ? (positiveValue.slice(0, separator) as AcceptedLookup) : null;
  const rawClause = category ? positiveValue.slice(separator + 1) : positiveValue;
  const parsed: ParsedFilter = {
    raw: value,
    category,
    rawClause,
    values: [],
    negated,
    editable: false,
    wildcard: false
  };

  // Only the editor's literal subset is safe to rewrite; leave arbitrary Lucene clauses opaque.
  if (!category || !/^[A-Za-z_][A-Za-z0-9_.]*$/.test(category)) {
    return parsed;
  }

  parsed.editable = true;

  if (rawClause === '*') {
    parsed.wildcard = true;
    return parsed;
  }

  if (/^[A-Za-z_][A-Za-z0-9_.]*$/.test(rawClause) && !/^(true|false|AND|OR|NOT)$/i.test(rawClause)) {
    parsed.values = [rawClause];
    return parsed;
  }

  const parts = parseQuotedValues(rawClause);
  if (!parts) {
    parsed.editable = false;
    return parsed;
  }

  parsed.values = parts;
  return parsed;
};

const serializeFilter = (category: string, values: string[], negated: boolean) => {
  const filter: string[] = [];

  if (negated) {
    filter.push('-');
  }

  filter.push(category + ':');

  const serializedValues = uniq(values)
    .map(item => `"${sanitizeLuceneQuery(item)}"`)
    .filter(item => !isEmpty(item));
  if (serializedValues.length > 1) {
    filter.push(`(${serializedValues.join(' OR ')})`);
  } else {
    filter.push(serializedValues[0] ?? '*');
  }

  return filter.join('');
};

const filterFields = createFilterOptions<string>();

const HitFilter: FC<{ size?: 'small' | 'medium'; id: number; value: string }> = ({ size, id, value }) => {
  const { t } = useTranslation();
  const { config } = useContext(ApiConfigContext);
  const { hitFields, getHitFields } = useContext(FieldContext);
  const { dispatchApi } = useMyApi();

  const setSavedFilter = useContextSelector(ParameterContext, ctx => ctx.setFilter);
  const removeSavedFilter = useContextSelector(ParameterContext, ctx => ctx.removeFilter);
  const disabledFilterIndexes = useContextSelector(ParameterContext, ctx => ctx.disabledFilterIndexes);
  const setFilterDisabled = useContextSelector(ParameterContext, ctx => ctx.setFilterDisabled);
  const disabled = disabledFilterIndexes?.includes(id) ?? false;

  const [parsedFilter, setParsedFilter] = useState(() => parseFilter(value));
  const [previousValue, setPreviousValue] = useState(value);
  // Synchronize external replacements without resetting edits when only lookup config changes.
  if (previousValue !== value) {
    setPreviousValue(value);
    setParsedFilter(parseFilter(value));
  }
  const [customLookups, setCustomLookups] = useState<{ category: string | null; options: string[] }>({
    category: null,
    options: []
  });
  const [categorySearchInput, setCategorySearchInput] = useState('');

  const { category, values: filterValues, editable, negated } = parsedFilter;
  const configuredLookup = category ? config.lookups?.[category as ApiAcceptedLookup] : undefined;
  const needsLookups = !!category && editable && !Array.isArray(configuredLookup);
  const loading = needsLookups && customLookups.category !== category;
  const categoryOptions = hitFields.map(field => field.key).filter((field): field is string => !!field);

  useEffect(() => {
    void getHitFields();
  }, [getHitFields]);

  useEffect(() => {
    if (value) {
      setSavedFilter(id, value);
    }
  }, [id, setSavedFilter, value]);

  useEffect(() => {
    if (!category || !editable || !isNil(configuredLookup)) {
      return;
    }

    // Ignore responses from a previous field or an unmounted editor.
    let active = true;
    void (async () => {
      try {
        const facets = await dispatchApi(
          api.search.facet.hit.post({ query: `${category}:*`, fields: [category], rows: 100 }),
          { throwError: false }
        );

        if (!active) {
          return;
        }

        setCustomLookups({ category, options: Object.keys((facets ?? {})[category] ?? {}) });
      } catch {
        if (active) {
          setCustomLookups({ category, options: [] });
        }
      }
    })();

    return () => {
      active = false;
    };
  }, [category, configuredLookup, dispatchApi, editable]);

  const commitFilter = useCallback(
    (nextValue: string) => {
      setParsedFilter(parseFilter(nextValue));
      setSavedFilter(id, nextValue);
    },
    [id, setSavedFilter]
  );

  const onCategoryChange: UseAutocompleteProps<string, false, true, false>['onChange'] = useCallback(
    (_, nextCategory) => {
      commitFilter(`${negated ? '-' : ''}${nextCategory}:*`);
    },
    [commitFilter, negated]
  );

  const onValuesChange: UseAutocompleteProps<string, true, false, true>['onChange'] = useCallback(
    (_, newValues) => {
      if (!category) {
        return;
      }

      commitFilter(serializeFilter(category, newValues, negated));
    },
    [category, commitFilter, negated]
  );

  const toggleNegation = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>, nextNegated: boolean) => {
      event.stopPropagation();
      // Toggle only the leading sign, including for opaque clauses the editor cannot parse.
      commitFilter(parsedFilter.raw.replace(/^-?/, nextNegated ? '-' : ''));
    },
    [commitFilter, parsedFilter.raw]
  );

  const lookupOptions = configuredLookup ?? (customLookups.category === category ? customLookups.options : []);
  const chipLabel = `${parsedFilter.category ? `${parsedFilter.category}:` : ''}${parsedFilter.rawClause}`;

  return (
    <Stack direction="row" alignItems="center" spacing={0.5}>
      <ChipPopper
        dimmed={disabled}
        icon={
          <Stack direction="row" spacing={0.25} alignItems="center">
            <FilterList fontSize="small" />
            {parsedFilter.negated ? (
              <Tooltip title={t('hit.search.filter.excluded')}>
                <RemoveCircleOutline fontSize="small" color="error" />
              </Tooltip>
            ) : (
              <Tooltip title={t('hit.search.filter.included')}>
                <AddCircleOutline fontSize="small" color="success" />
              </Tooltip>
            )}
          </Stack>
        }
        label={<Typography variant="body2">{chipLabel}</Typography>}
        minWidth="250px"
        onDelete={() => removeSavedFilter(value)}
        slotProps={{ chip: { size: 'small', color: parsedFilter.wildcard ? 'warning' : 'default' } }}
      >
        <Stack spacing={1} sx={{ minWidth: '225px' }}>
          <FormControlLabel
            label={t('hit.search.filter.disable')}
            control={
              <Checkbox
                size="small"
                checked={disabled}
                onChange={(_event, checked) => setFilterDisabled(id, checked)}
              />
            }
          />
          <FormControlLabel
            label={t('hit.search.filter.exclude')}
            control={<Checkbox size="small" checked={negated} onChange={toggleNegation} />}
          />
          <Autocomplete
            fullWidth
            disableClearable
            disabled={!editable}
            size={size ?? 'small'}
            value={category ?? ACCEPTED_LOOKUPS[0]}
            options={categoryOptions}
            filterOptions={(options, state) =>
              categorySearchInput
                ? filterFields(options, { ...state, inputValue: categorySearchInput })
                : options.filter(option => DEFAULT_FILTER_FIELDS.includes(option))
            }
            renderInput={_params => <TextField {..._params} label={t('hit.search.filter.fields')} />}
            onChange={onCategoryChange}
            onInputChange={(_event, inputValue, reason) => setCategorySearchInput(reason === 'input' ? inputValue : '')}
          />
          <Autocomplete<string, true, false, true>
            fullWidth
            freeSolo
            multiple
            disabled={!category || !editable}
            loading={loading}
            size={size ?? 'small'}
            value={filterValues}
            options={lookupOptions}
            renderInput={_params => <TextField {..._params} label={t('hit.search.filter.values')} />}
            getOptionLabel={option => t(option)}
            onChange={onValuesChange}
          />
        </Stack>
      </ChipPopper>
    </Stack>
  );
};

export default memo(HitFilter);
