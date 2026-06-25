import { Chip, Grid, Skeleton, Stack, Typography } from '@mui/material';
import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import type { Case } from 'models/entities/generated/Case';
import type { Event } from 'models/entities/generated/Event';
import type { Hit } from 'models/entities/generated/Hit';
import type { Related } from 'models/entities/generated/Related';
import { memo, useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useOutletContext } from 'react-router-dom';
import useCase from '../hooks/useCase';
import Observable, { type ObservableEntry, type ObservableType } from './observables/Observable';

/** All Related fields that carry observable values */
const OBSERVABLE_FIELDS: ObservableType[] = ['hash', 'hosts', 'ip', 'user', 'ids', 'id', 'uri', 'signature'];

/** Extract (type, value, seenInId) triples from a record's related field */
const extractObservables = (
  related: Related | undefined,
  recordId: string
): { type: ObservableType; value: string; id: string }[] => {
  if (!related) {
    return [];
  }

  const results: { type: ObservableType; value: string; id: string }[] = [];
  for (const field of OBSERVABLE_FIELDS) {
    const raw = related[field];
    if (!raw) {
      continue;
    }

    const values = Array.isArray(raw) ? raw : [raw];
    for (const value of values) {
      if (value) {
        results.push({ type: field, value: String(value), id: recordId });
      }
    }
  }

  return results;
};

/** Deduplicate and merge seenIn lists into a map keyed by `type:value` */
export const buildObservableEntries = (records: Partial<Hit | Event>[]): ObservableEntry[] => {
  const map = new Map<string, ObservableEntry>();

  for (const record of records) {
    const related = (record as Hit).related ?? (record as Event).related;
    const recordId = (record as Hit).howler?.id ?? (record as Event).howler?.id;
    if (!recordId) {
      continue;
    }

    for (const { type, value, id } of extractObservables(related, recordId)) {
      const key = `${type}:${value}`;
      if (!map.has(key)) {
        map.set(key, { type, value, seenIn: [] });
      }

      const entry = map.get(key)!;
      if (!entry.seenIn.includes(id)) {
        entry.seenIn.push(id);
      }
    }
  }

  return Array.from(map.values());
};

const RELATED_FIELDS = OBSERVABLE_FIELDS.map(f => `related.${f}`).join(',');

const CaseObservables: FC<{ case?: Case; caseId?: string }> = ({ case: providedCase, caseId }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const routeCase = useOutletContext<Case>();
  const { case: _case } = useCase({ case: providedCase ?? routeCase, caseId });

  const [records, setRecords] = useState<Partial<Hit | Event>[] | null>(null);
  const [activeFilters, setActiveFilters] = useState<Set<ObservableType>>(new Set());

  const ids = useMemo(
    () =>
      (_case?.items ?? [])
        .filter(item => ['hit', 'event'].includes(item.type))
        .map(item => item.value)
        .filter(val => !!val),
    [_case?.items]
  );

  useEffect(() => {
    if (ids.length < 1) {
      setRecords([]);
      return;
    }
    dispatchApi(
      api.v2.search.post<Hit | Event>(['hit', 'event'], {
        query: `howler.id:(${ids.join(' OR ')})`,
        fl: `howler.id,${RELATED_FIELDS}`
      })
    ).then(response => setRecords(response.items));
  }, [dispatchApi, ids]);

  const allObservables = useMemo(() => (records ? buildObservableEntries(records) : []), [records]);

  const observableTypes = useMemo(
    () => (allObservables ? ([...new Set(allObservables.map(a => a.type))] as ObservableType[]).sort() : []),
    [allObservables]
  );

  const filteredObservables = useMemo(() => {
    if (allObservables.length < 1) {
      return [];
    }

    if (activeFilters.size === 0) {
      return allObservables;
    }

    return allObservables.filter(a => activeFilters.has(a.type));
  }, [allObservables, activeFilters]);

  const toggleFilter = (type: ObservableType) => {
    setActiveFilters(prev => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  };

  if (!_case) {
    return null;
  }

  return (
    <Grid container spacing={2} px={2}>
      <Grid item xs={12}>
        <Stack direction="row" alignItems="center" spacing={1} flexWrap="wrap">
          <Typography variant="subtitle2" color="text.secondary">
            {t('page.cases.observables.filter_by_type')}
          </Typography>
          {records === null ? (
            <Skeleton width={240} height={32} />
          ) : (
            observableTypes.map(type => (
              <Chip
                key={type}
                label={t(`page.cases.observables.type.${type}`)}
                size="small"
                onClick={() => toggleFilter(type)}
                color={activeFilters.has(type) ? 'primary' : 'default'}
                variant={activeFilters.has(type) ? 'filled' : 'outlined'}
              />
            ))
          )}
        </Stack>
      </Grid>
      {records === null ? (
        Array.from({ length: 6 }, (_, i) => (
          <Grid key={`skeleton-${i}`} item xs={12} sm={6} md={4} xl={3}>
            <Skeleton height={100} />
          </Grid>
        ))
      ) : filteredObservables.length === 0 ? (
        <Grid item xs={12}>
          <Typography color="text.secondary">{t('page.cases.observables.empty')}</Typography>
        </Grid>
      ) : (
        filteredObservables.map(observable => (
          <Grid key={`${observable.type}:${observable.value}`} item xs={12} md={6} xl={4}>
            <Observable asset={observable} case={_case} />
          </Grid>
        ))
      )}
    </Grid>
  );
};

export default memo(CaseObservables);
