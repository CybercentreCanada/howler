import { AddCircleOutline, FilterList, RemoveCircleOutline } from '@mui/icons-material';
import type { UseAutocompleteProps } from '@mui/material';
import { Autocomplete, Checkbox, FormControlLabel, Stack, TextField, Tooltip, Typography } from '@mui/material';
import api from 'api';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import ChipPopper from 'components/elements/display/ChipPopper';
import useMyApi from 'components/hooks/useMyApi';
import { uniq } from 'lodash-es';
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
];

interface ParsedFilter {
  raw: string;
  category: string | null;
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
  const category = separator > 0 ? positiveValue.slice(0, separator) : null;
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

  const serializedValues = uniq(values).map(item => `"${sanitizeLuceneQuery(item)}"`);
  if (serializedValues.length > 1) {
    filter.push(`(${serializedValues.join(' OR ')})`);
  } else {
    filter.push(serializedValues[0] ?? '*');
  }

  return filter.join('');
};

const HitFilter: FC<{ size?: 'small' | 'medium'; id: number; value: string }> = ({ size, id, value }) => {
  const { t } = useTranslation();
  const { config } = useContext(ApiConfigContext);
  const { dispatchApi } = useMyApi();

  const setSavedFilter = useContextSelector(ParameterContext, ctx => ctx.setFilter);
  const removeSavedFilter = useContextSelector(ParameterContext, ctx => ctx.removeFilter);

  const [parsedFilter, setParsedFilter] = useState(() => parseFilter(value));
  const [previousValue, setPreviousValue] = useState(value);
  // Synchronize external replacements without resetting edits when only lookup config changes.
  if (previousValue !== value) {
    setPreviousValue(value);
    setParsedFilter(parseFilter(value));
  }
  const { category, values: filterValues, editable, negated } = parsedFilter;
  const [customLookups, setCustomLookups] = useState<{ category: string | null; options: string[] }>({
    category: null,
    options: []
  });
  const configuredLookup = category ? config.lookups?.[category as keyof APILookups] : undefined;
  const needsLookups = Boolean(category && editable && !Array.isArray(configuredLookup));
  const loading = needsLookups && customLookups.category !== category;

  useEffect(() => {
    if (value) setSavedFilter(id, value);
  }, [id, setSavedFilter, value]);

  useEffect(() => {
    if (!category || !editable || Array.isArray(configuredLookup)) {
      return;
    }

    // Ignore responses from a previous field or an unmounted editor.
    let active = true;
    const fetchLookups = async () => {
      try {
        const facets = await dispatchApi(
          api.search.facet.hit.post({ query: `${category}:*`, fields: [category], rows: 100 }),
          { throwError: false }
        );

        if (active) {
          setCustomLookups({ category, options: Object.keys((facets ?? {})[category] ?? {}) });
        }
      } catch {
        // A failed suggestion request must not prevent free-text filter editing.
        if (active) setCustomLookups({ category, options: [] });
      }
    };

    void fetchLookups();
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
      if (category) {
        commitFilter(serializeFilter(category, newValues, negated));
      }
    },
    [category, commitFilter, negated]
  );

  const toggleNegation = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>, nextNegated: boolean) => {
      event.stopPropagation();
      // Toggle only the leading sign, including for opaque clauses the editor cannot parse.
      const positiveValue = negated ? parsedFilter.raw.slice(1) : parsedFilter.raw;
      commitFilter(`${nextNegated ? '-' : ''}${positiveValue}`);
    },
    [commitFilter, negated, parsedFilter.raw]
  );

  const lookupOptions = Array.isArray(configuredLookup)
    ? configuredLookup
    : customLookups.category === category
      ? customLookups.options
      : [];
  const chipLabel = `${parsedFilter.category ? `${parsedFilter.category}:` : ''}${parsedFilter.rawClause}`;

  return (
    <Stack direction="row" alignItems="center" spacing={0.5}>
      <ChipPopper
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
            label={t('hit.search.filter.exclude')}
            control={<Checkbox size="small" checked={negated} onChange={toggleNegation} />}
          />
          <Autocomplete
            fullWidth
            disableClearable
            disabled={!editable}
            size={size ?? 'small'}
            value={category ?? ''}
            options={ACCEPTED_LOOKUPS}
            renderInput={_params => <TextField {..._params} label={t('hit.search.filter.fields')} />}
            onChange={onCategoryChange}
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
