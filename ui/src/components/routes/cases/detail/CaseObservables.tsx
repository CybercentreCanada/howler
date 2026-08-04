import { FilterList } from '@mui/icons-material';
import { Chip, Grid, Skeleton, Stack, TextField, Typography } from '@mui/material';
import api from 'api';
import ChipPopper from 'components/elements/display/ChipPopper';
import useMyApi from 'components/hooks/useMyApi';
import { toArray, uniq } from 'lodash-es';
import type { Case } from 'models/entities/generated/Case';
import type { Event } from 'models/entities/generated/Event';
import type { Hit } from 'models/entities/generated/Hit';
import { memo, useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useOutletContext } from 'react-router-dom';
import useCase from '../hooks/useCase';
import ObservableTable from './observables/ObservableTable';
import type { ObservableRole, ObservableType, OriginType } from './types';
import { OBSERVABLE_FIELDS, buildObservableEntries } from './utils';

const RELATED_FIELDS = OBSERVABLE_FIELDS.map(f => `related.${f}`).join(',');
const EXTRA_FIELDS =
  'howler.escalation,howler.outline.threat,howler.outline.target,howler.outline.indicators,threat.indicator.ip,threat.indicator.description';

const CaseObservables: FC<{ case?: Case; caseId?: string }> = ({ case: providedCase, caseId }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const routeCase = useOutletContext<Case>();
  const { case: _case } = useCase({ case: providedCase ?? routeCase, caseId });

  const [records, setRecords] = useState<(Hit | Event)[] | null>(null);
  const [activeFilters, setActiveFilters] = useState<ObservableType[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [originFilters, setOriginFilters] = useState<OriginType[]>([]);
  const [roleFilters, setRoleFilters] = useState<ObservableRole[]>([]);
  const [escalationOptions, setEscalationOptions] = useState<string[]>([]);
  const [activeEscalations, setActiveEscalations] = useState<string[]>([]);

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

    void dispatchApi(
      api.v2.search.post<Hit | Event>(['hit', 'event'], {
        query: `howler.id:(${ids.join(' OR ')})`,
        fl: `howler.id,${RELATED_FIELDS},${EXTRA_FIELDS}`
      }),
      { throwError: false, showError: true }
    ).then(response => response && setRecords(response.items));
  }, [dispatchApi, ids]);

  useEffect(() => {
    if (ids.length < 1) {
      setEscalationOptions([]);
      setActiveEscalations([]);
      return;
    }

    void dispatchApi(
      api.v2.search.facet.post(['hit', 'event'], {
        fields: ['howler.escalation'],
        filters: [`howler.id:(${ids.join(' OR ')})`]
      }),
      { throwError: false }
    ).then(result => {
      if (result) {
        setEscalationOptions(Object.keys(result['howler.escalation'] ?? {}));
      }
    });
  }, [dispatchApi, ids]);

  const allObservables = useMemo(() => {
    if (!_case) {
      return [];
    }

    if (!records?.length) {
      return [];
    }

    return buildObservableEntries(_case, records);
  }, [records, _case]);

  const observableTypes = useMemo(
    () => (allObservables ? (uniq(allObservables.map(a => a.type)) as ObservableType[]).sort() : []),
    [allObservables]
  );

  const filteredObservables = useMemo(() => {
    if (allObservables.length < 1) {
      return [];
    }

    let result = allObservables;

    if (activeFilters.length > 0) {
      result = result.filter(a => activeFilters.includes(a.type));
    }

    if (searchQuery.trim()) {
      const query = searchQuery.trim().toLowerCase();
      result = result.filter(a => a.value.toLowerCase().includes(query) || a.type.toLowerCase().includes(query));
    }

    if (originFilters.length > 0) {
      result = result.filter(a => a.sources?.some(s => originFilters.includes(s.type as OriginType)));
    }

    if (activeEscalations.length > 0) {
      result = result.filter(a => a.sources?.some(s => s.escalation && activeEscalations.includes(s.escalation)));
    }

    if (roleFilters.length > 0) {
      result = result.filter(a => a.role && roleFilters.includes(a.role));
    }

    return result;
  }, [allObservables, activeFilters, searchQuery, originFilters, activeEscalations, roleFilters]);

  const toggleSetItem = <T,>(setter: (updater: (prev: T[]) => T[]) => void, item: T) => {
    setter(prev => {
      if (prev.includes(item)) {
        return prev.filter(_item => _item !== item);
      } else {
        return [...prev, item];
      }
    });
  };

  if (!_case) {
    return null;
  }

  return (
    <Grid container spacing={2} px={2}>
      <Grid item xs={12}>
        <Stack spacing={1.5}>
          <TextField
            size="small"
            placeholder={t('page.cases.observables.search')}
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            sx={{ maxWidth: 360 }}
            id="observable-search"
          />
          <Stack direction="row" spacing={1} flexWrap="wrap">
            <ChipPopper
              icon={<FilterList />}
              label={
                activeFilters.length > 0
                  ? `${t('page.cases.observables.filter_by_type')} (${toArray(activeFilters)
                      .map(type => t(`page.cases.observables.type.${type}`))
                      .sort()
                      .join(', ')})`
                  : t('page.cases.observables.filter_by_type')
              }
              slotProps={{
                chip: { size: 'small', color: activeFilters.length > 0 ? 'primary' : 'default' }
              }}
            >
              {records === null ? (
                <Skeleton width={200} height={32} />
              ) : (
                <Stack direction="row" gap={0.5} flexWrap="wrap">
                  {observableTypes.map(type => (
                    <Chip
                      key={type}
                      label={t(`page.cases.observables.type.${type}`)}
                      size="small"
                      onClick={() => toggleSetItem(setActiveFilters, type)}
                      color={activeFilters.includes(type) ? 'primary' : 'default'}
                      variant={activeFilters.includes(type) ? 'filled' : 'outlined'}
                    />
                  ))}
                </Stack>
              )}
            </ChipPopper>
            <ChipPopper
              icon={<FilterList />}
              label={
                originFilters.length > 0
                  ? `${t('page.cases.observables.filter_by_origin')} (${toArray(originFilters).join(', ')})`
                  : t('page.cases.observables.filter_by_origin')
              }
              slotProps={{
                chip: { size: 'small', color: originFilters.length > 0 ? 'primary' : 'default' }
              }}
            >
              <Stack direction="row" gap={0.5} flexWrap="wrap">
                {(['hit', 'event'] as OriginType[]).map(origin => (
                  <Chip
                    key={origin}
                    label={t(`page.cases.observables.origin.${origin}`)}
                    size="small"
                    onClick={() => toggleSetItem(setOriginFilters, origin)}
                    color={originFilters.includes(origin) ? 'primary' : 'default'}
                    variant={originFilters.includes(origin) ? 'filled' : 'outlined'}
                  />
                ))}
              </Stack>
            </ChipPopper>
            <ChipPopper
              icon={<FilterList />}
              label={
                roleFilters.length > 0
                  ? `${t('page.cases.observables.filter_by_role')} (${toArray(roleFilters).join(', ')})`
                  : t('page.cases.observables.filter_by_role')
              }
              slotProps={{
                chip: { size: 'small', color: roleFilters.length > 0 ? 'primary' : 'default' }
              }}
            >
              <Stack direction="row" gap={0.5} flexWrap="wrap">
                {(['threat', 'target', 'indicator'] as ObservableRole[]).map(role => (
                  <Chip
                    key={role}
                    label={t(`page.cases.observables.role.${role}`)}
                    size="small"
                    onClick={() => toggleSetItem(setRoleFilters, role)}
                    color={roleFilters.includes(role) ? 'primary' : 'default'}
                    variant={roleFilters.includes(role) ? 'filled' : 'outlined'}
                  />
                ))}
              </Stack>
            </ChipPopper>
            {escalationOptions.length > 0 && (
              <ChipPopper
                icon={<FilterList />}
                label={
                  activeEscalations.length > 0
                    ? `${t('page.cases.observables.filter_by_escalation')} (${toArray(activeEscalations).join(', ')})`
                    : t('page.cases.observables.filter_by_escalation')
                }
                slotProps={{
                  chip: {
                    size: 'small',
                    color: activeEscalations.length > 0 ? 'primary' : 'default'
                  }
                }}
              >
                <Stack direction="row" gap={0.5} flexWrap="wrap">
                  {escalationOptions.map(esc => (
                    <Chip
                      key={esc}
                      label={esc}
                      size="small"
                      onClick={() => toggleSetItem(setActiveEscalations, esc)}
                      color={activeEscalations.includes(esc) ? 'primary' : 'default'}
                      variant={activeEscalations.includes(esc) ? 'filled' : 'outlined'}
                    />
                  ))}
                </Stack>
              </ChipPopper>
            )}
          </Stack>
        </Stack>
      </Grid>
      {records === null ? (
        Array.from({ length: 6 }, (_, i) => (
          <Grid key={`skeleton-${i}`} item xs={12}>
            <Skeleton height={40} />
          </Grid>
        ))
      ) : filteredObservables.length === 0 ? (
        <Grid item xs={12}>
          <Typography color="text.secondary">{t('page.cases.observables.empty')}</Typography>
        </Grid>
      ) : (
        <Grid item xs={12}>
          <ObservableTable observables={filteredObservables} case={_case} />
        </Grid>
      )}
    </Grid>
  );
};

export default memo(CaseObservables);
