import { AddCircleOutline, FilterList, RemoveCircleOutline } from '@mui/icons-material';
import type { UseAutocompleteProps } from '@mui/material';
import { Autocomplete, IconButton, Stack, TextField, Typography } from '@mui/material';
import api from 'api';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import ChipPopper from 'components/elements/display/ChipPopper';
import useMyApi from 'components/hooks/useMyApi';
import type { APILookups } from 'models/entities/generated/ApiType';
import type { FC } from 'react';
import { memo, useCallback, useContext, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useContextSelector } from 'use-context-selector';
import { sanitizeLuceneQuery } from 'utils/stringUtils';

const ACCEPTED_LOOKUPS = [
  'howler.assessment',
  'howler.escalation',
  'howler.analytic',
  'howler.detection',
  'event.provider',
  'organization.name'
];
const WILDCARD_OPTION = '\u0000howler-wildcard';

interface ParsedFilter {
  category: string | null;
  rawClause: string;
  values: string[];
  rawValues: string[];
  grouped: boolean;
  negated: boolean;
  editable: boolean;
  wildcard: boolean;
}

const unescapeLucene = (value: string) => value.replace(/\\(.)/gs, '$1');

const parseQuotedValue = (value: string) => {
  const match = value.match(/^"((?:\\.|[^"\\])*)"$/s);
  return match ? { value: unescapeLucene(match[1] ?? ''), raw: value } : null;
};

const parseQuotedGroup = (value: string) => {
  const parts: { value: string; raw: string }[] = [];
  let remaining = value;

  while (remaining) {
    const match = remaining.match(/^"((?:\\.|[^"\\])*)"(?: OR |$)/s);
    if (!match) {
      return null;
    }
    if (match[0].endsWith(' OR ') && match[0].length === remaining.length) {
      return null;
    }

    parts.push({
      value: unescapeLucene(match[1] ?? ''),
      raw: match[0].endsWith(' OR ') ? match[0].slice(0, -4) : match[0]
    });
    remaining = remaining.slice(match[0].length);
  }

  return parts.length ? parts : null;
};

const parseFilter = (value: string): ParsedFilter => {
  const negated = value.startsWith('-');
  const positiveValue = negated ? value.slice(1) : value;
  const separator = positiveValue.indexOf(':');
  if (separator <= 0) {
    return {
      category: null,
      rawClause: positiveValue,
      values: [],
      rawValues: [],
      grouped: false,
      negated,
      editable: false,
      wildcard: false
    };
  }

  const category = positiveValue.slice(0, separator);
  const rawClause = positiveValue.slice(separator + 1);
  if (rawClause === '*') {
    return { category, rawClause, values: [], rawValues: [], grouped: false, negated, editable: true, wildcard: true };
  }

  const scalar = parseQuotedValue(rawClause);
  if (scalar !== null) {
    return {
      category,
      rawClause,
      values: [scalar.value],
      rawValues: [scalar.raw],
      grouped: false,
      negated,
      editable: true,
      wildcard: false
    };
  }

  if (/^[A-Za-z_][A-Za-z0-9_.]*$/.test(rawClause) && !/^(true|false)$/i.test(rawClause)) {
    return {
      category,
      rawClause,
      values: [rawClause],
      rawValues: [rawClause],
      grouped: false,
      negated,
      editable: true,
      wildcard: false
    };
  }

  if (rawClause.startsWith('(') && rawClause.endsWith(')')) {
    const groupedValues = parseQuotedGroup(rawClause.slice(1, -1));
    if (groupedValues) {
      return {
        category,
        rawClause,
        values: groupedValues.map(item => item.value),
        rawValues: groupedValues.map(item => item.raw),
        grouped: true,
        negated,
        editable: true,
        wildcard: false
      };
    }
  }

  return { category, rawClause, values: [], rawValues: [], grouped: false, negated, editable: false, wildcard: false };
};

const serializeFilter = (
  category: string,
  values: string[],
  grouped: boolean,
  negated: boolean,
  wildcard: boolean,
  previousValues: string[],
  previousRawValues: string[]
) => {
  const prefix = negated ? '-' : '';
  if (wildcard) {
    return `${prefix}${category}:*`;
  }

  const reusedValues = new Set<number>();
  const serializedValues = values.map(item => {
    const previousIndex = previousValues.findIndex((previous, index) => previous === item && !reusedValues.has(index));
    if (previousIndex >= 0) {
      reusedValues.add(previousIndex);
      return previousRawValues[previousIndex] ?? `"${sanitizeLuceneQuery(item)}"`;
    }
    return `"${sanitizeLuceneQuery(item)}"`;
  });
  const clause = grouped ? `(${serializedValues.join(' OR ')})` : (serializedValues[0] ?? '*');
  return `${prefix}${category}:${clause}`;
};

const HitFilter: FC<{ size?: 'small' | 'medium'; id: number; value: string }> = ({ size, id, value }) => {
  const { t } = useTranslation();
  const { config } = useContext(ApiConfigContext);
  const { dispatchApi } = useMyApi();

  const setSavedFilter = useContextSelector(ParameterContext, ctx => ctx.setFilter);
  const removeSavedFilter = useContextSelector(ParameterContext, ctx => ctx.removeFilter);

  const [rawFilter, setRawFilter] = useState(value);
  const parsedFilter = parseFilter(rawFilter);
  const [category, setCategory] = useState<string | null>(parsedFilter.category);
  const [filterValues, setFilterValues] = useState<string[]>(parsedFilter.values);
  const [rawValues, setRawValues] = useState<string[]>(parsedFilter.rawValues);
  const [grouped, setGrouped] = useState(parsedFilter.grouped);
  const [editable, setEditable] = useState(parsedFilter.editable);
  const [wildcard, setWildcard] = useState(parsedFilter.wildcard);
  const negated = parsedFilter.negated;
  const [loading, setLoading] = useState(false);

  const [customLookups, setCustomLookups] = useState<string[]>([]);

  useEffect(() => {
    if (value) {
      const parsed = parseFilter(value);
      setRawFilter(value);
      setCategory(parsed.category);
      setFilterValues(parsed.values);
      setRawValues(parsed.rawValues);
      setGrouped(parsed.grouped);
      setEditable(parsed.editable);
      setWildcard(parsed.wildcard);
      setSavedFilter(id, value);
    }
  }, [id, setSavedFilter, value]);

  const onCategoryChange: UseAutocompleteProps<string, false, false, false>['onChange'] = useCallback(
    async (_, _category) => {
      setCategory(_category);
      setFilterValues([]);
      setRawValues([]);
      setWildcard(false);

      if (!_category) {
        return;
      }

      if (!config.lookups?.[_category as keyof APILookups]) {
        setLoading(true);

        const facets = await dispatchApi(
          api.search.facet.hit.post({ query: 'howler.id:*', fields: [_category], rows: 100 }),
          {
            throwError: false
          }
        );

        setCustomLookups(Object.keys((facets ?? {})[_category] ?? {}));
        setLoading(false);
      } else {
        setCustomLookups([]);
      }
    },
    [config.lookups, dispatchApi]
  );

  const onValueChange: UseAutocompleteProps<string, false, false, true>['onChange'] = useCallback(
    (_, newValue) => {
      const isWildcard = !newValue || newValue === WILDCARD_OPTION;
      const values = isWildcard ? [] : [newValue];
      setFilterValues(values);
      setWildcard(isWildcard);

      if (category) {
        const nextValue = serializeFilter(category, values, grouped, negated, isWildcard, filterValues, rawValues);
        setRawValues(parseFilter(nextValue).rawValues);
        setRawFilter(nextValue);
        setSavedFilter(id, nextValue);
      }
    },
    [category, filterValues, grouped, id, negated, rawValues, setSavedFilter]
  );

  const onGroupedValueChange: UseAutocompleteProps<string, true, false, true>['onChange'] = useCallback(
    (_, newValues) => {
      const isWildcard = newValues.length === 0 || (newValues.length === 1 && newValues[0] === WILDCARD_OPTION);
      const values = isWildcard ? [] : newValues.filter(newValue => newValue !== WILDCARD_OPTION);
      setFilterValues(values);
      setWildcard(isWildcard);

      if (category) {
        const nextValue = serializeFilter(category, values, true, negated, isWildcard, filterValues, rawValues);
        setRawValues(parseFilter(nextValue).rawValues);
        setRawFilter(nextValue);
        setSavedFilter(id, nextValue);
      }
    },
    [category, filterValues, id, negated, rawValues, setSavedFilter]
  );

  const toggleNegation = useCallback(
    (event: React.MouseEvent<HTMLButtonElement>) => {
      event.stopPropagation();
      const nextNegated = !negated;
      const positiveValue = rawFilter.startsWith('-') ? rawFilter.slice(1) : rawFilter;
      const nextValue = `${nextNegated ? '-' : ''}${positiveValue}`;
      setRawFilter(nextValue);
      setSavedFilter(id, nextValue);
    },
    [id, negated, rawFilter, setSavedFilter]
  );

  const configuredLookup =
    category && category in (config.lookups ?? {}) ? config.lookups?.[category as keyof APILookups] : undefined;
  const lookupOptions = Array.isArray(configuredLookup) ? configuredLookup : customLookups;
  const filterOptions = [...lookupOptions, ...(wildcard || !filterValues.includes('*') ? [WILDCARD_OPTION] : [])];
  const chipLabel = `${parsedFilter.negated ? '-' : ''}${parsedFilter.category ? `${parsedFilter.category}:` : ''}${parsedFilter.rawClause}`;

  return (
    <Stack direction="row" alignItems="center" spacing={0.5}>
      <ChipPopper
        icon={<FilterList fontSize="small" />}
        label={<Typography variant="body2">{chipLabel}</Typography>}
        minWidth="250px"
        onDelete={() => removeSavedFilter(value)}
        slotProps={{ chip: { size: 'small', color: parsedFilter.wildcard ? 'warning' : 'default' } }}
      >
        <Stack spacing={1} sx={{ minWidth: '225px' }}>
          <Autocomplete
            fullWidth
            disabled={!editable}
            size={size ?? 'small'}
            value={category}
            options={ACCEPTED_LOOKUPS}
            renderInput={_params => <TextField {..._params} label={t('hit.search.filter.fields')} />}
            onChange={onCategoryChange}
          />
          {grouped ? (
            <Autocomplete<string, true, false, true>
              fullWidth
              freeSolo
              multiple
              disabled={!category || !editable}
              loading={loading}
              size={size ?? 'small'}
              value={filterValues}
              options={filterOptions}
              renderInput={_params => <TextField {..._params} label={t('hit.search.filter.values')} />}
              getOptionLabel={option => (option === WILDCARD_OPTION ? '*' : t(option))}
              onChange={onGroupedValueChange}
            />
          ) : (
            <Autocomplete<string, false, false, true>
              fullWidth
              freeSolo
              disabled={!category || !editable}
              loading={loading}
              size={size ?? 'small'}
              value={wildcard ? '' : (filterValues[0] ?? '')}
              options={filterOptions}
              renderInput={_params => <TextField {..._params} label={t('hit.search.filter.values')} />}
              getOptionLabel={option => (option === WILDCARD_OPTION ? '*' : t(option))}
              onChange={onValueChange}
            />
          )}
        </Stack>
      </ChipPopper>
      <IconButton
        size="small"
        aria-label={t(negated ? 'hit.search.filter.include' : 'hit.search.filter.exclude')}
        title={t(negated ? 'hit.search.filter.include' : 'hit.search.filter.exclude')}
        onClick={toggleNegation}
      >
        {negated ? <AddCircleOutline fontSize="small" /> : <RemoveCircleOutline fontSize="small" />}
      </IconButton>
    </Stack>
  );
};

export default memo(HitFilter);
