import { FilterList } from '@mui/icons-material';
import { Chip, Grid, Skeleton, Stack, TextField, Typography } from '@mui/material';
import api from 'api';
import ChipPopper from 'components/elements/display/ChipPopper';
import useMyApi from 'components/hooks/useMyApi';
import { toArray, uniq } from 'lodash-es';
import type { Case } from 'models/entities/generated/Case';
import type { Hit } from 'models/entities/generated/Hit';
import type { Observable } from 'models/entities/generated/Observable';
import type { Related } from 'models/entities/generated/Related';
import { memo, useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useOutletContext } from 'react-router-dom';
import useCase from '../hooks/useCase';
import { type AssetEntry, type AssetRole, type AssetSource, type AssetType } from './assets/Asset';
import AssetTable from './assets/AssetTable';

/** All Related fields that carry asset values */
const ASSET_FIELDS: AssetType[] = ['hash', 'hosts', 'ip', 'user', 'ids', 'id', 'uri', 'signature'];

/** Extract (type, value, seenInId) triples from a record's related field */
const extractAssets = (
  related: Related | undefined,
  recordId: string
): { type: AssetType; value: string; id: string }[] => {
  if (!related) {
    return [];
  }

  const results: { type: AssetType; value: string; id: string }[] = [];
  for (const field of ASSET_FIELDS) {
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
export const buildAssetEntries = (records: Partial<Hit | Observable>[]): AssetEntry[] => {
  const map = new Map<string, AssetEntry>();

  for (const record of records) {
    const related = (record as Hit).related ?? (record as Observable).related;
    const recordId = (record as Hit).howler?.id ?? (record as Observable).howler?.id;
    if (!recordId) {
      continue;
    }

    for (const { type, value, id } of extractAssets(related, recordId)) {
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

const RELATED_FIELDS = ASSET_FIELDS.map(f => `related.${f}`).join(',');
const EXTRA_FIELDS =
  'howler.escalation,howler.outline.threat,howler.outline.target,howler.outline.indicators,threat.indicator.ip,threat.indicator.description';

type OriginType = 'hit' | 'observable';

/**
 * Classify an asset's role based on case-level lists and per-record outline fields.
 *
 * Resolution order:
 * 1. Case-level `threats[]`, `targets[]`, `indicators[]` (authoritative).
 * 2. Per-record `outline.threat` / `outline.target` (exact match).
 * 3. Per-record `outline.indicators[]`, `threat.indicator.ip/.description`.
 * 4. Default: "indicator" — all assets come from `related.*` fields which are IOCs by nature.
 *
 * Comparison is case-insensitive and trimmed.
 */
export const classifyRole = (value: string, _case: Case, records: Partial<Hit | Observable>[]): AssetRole => {
  const normalized = value.trim().toLowerCase();

  // Case-level classification (most authoritative)
  if (_case.threats?.some(t => String(t).trim().toLowerCase() === normalized)) {
    return 'threat';
  }

  if (_case.targets?.some(t => String(t).trim().toLowerCase() === normalized)) {
    return 'target';
  }

  if (_case.indicators?.some(i => String(i).trim().toLowerCase() === normalized)) {
    return 'indicator';
  }

  // Per-record outline checks
  for (const record of records) {
    const outline = (record as Hit).howler?.outline;

    if (outline?.threat && String(outline.threat).trim().toLowerCase() === normalized) {
      return 'threat';
    }

    if (outline?.target && String(outline.target).trim().toLowerCase() === normalized) {
      return 'target';
    }

    if (outline?.indicators?.some(ind => String(ind).trim().toLowerCase() === normalized)) {
      return 'indicator';
    }

    const indicator = (record as Hit).threat?.indicator;
    if (indicator) {
      const indicatorIp = indicator.ip?.trim().toLowerCase();
      const indicatorDesc = indicator.description?.trim().toLowerCase();
      if ((indicatorIp && indicatorIp === normalized) || (indicatorDesc && indicatorDesc === normalized)) {
        return 'indicator';
      }
    }
  }

  // Default: assets from related.* are IOCs
  return 'indicator';
};

/** Resolve source metadata for an asset's seenIn IDs */
const resolveSources = (
  seenIn: string[],
  caseItems: Case['items'],
  escalationMap: Map<string, string>
): AssetSource[] => {
  return seenIn
    .map(id => {
      const item = caseItems.find(i => i.value === id);
      if (!item) {
        return null;
      }
      return {
        id,
        type: item.type as 'hit' | 'observable' | 'case',
        path: item.path,
        escalation: escalationMap.get(id)
      };
    })
    .filter(Boolean) as AssetSource[];
};

const CaseAssets: FC<{ case?: Case; caseId?: string }> = ({ case: providedCase, caseId }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const routeCase = useOutletContext<Case>();
  const { case: _case } = useCase({ case: providedCase ?? routeCase, caseId });

  const [records, setRecords] = useState<Partial<Hit | Observable>[] | null>(null);
  const [activeFilters, setActiveFilters] = useState<Set<AssetType>>(new Set());
  const [searchQuery, setSearchQuery] = useState('');
  const [originFilters, setOriginFilters] = useState<Set<OriginType>>(new Set());
  const [roleFilters, setRoleFilters] = useState<Set<AssetRole>>(new Set());
  const [escalationOptions, setEscalationOptions] = useState<string[]>([]);
  const [activeEscalations, setActiveEscalations] = useState<Set<string>>(new Set());
  const [escalationMap, setEscalationMap] = useState<Map<string, string>>(new Map());

  const ids = useMemo(
    () =>
      (_case?.items ?? [])
        .filter(item => ['hit', 'observable'].includes(item.type))
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
      api.v2.search.post<Hit | Observable>(['hit', 'observable'], {
        query: `howler.id:(${ids.join(' OR ')})`,
        fl: `howler.id,${RELATED_FIELDS},${EXTRA_FIELDS}`
      })
    ).then(response => {
      setRecords(response.items);

      // Build escalation map from fetched records
      const escMap = new Map<string, string>();
      for (const record of response.items) {
        const id = (record as Hit).howler?.id ?? (record as Observable).howler?.id;
        const escalation = (record as Hit).howler?.escalation;
        if (id && escalation) {
          escMap.set(id, escalation);
        }
      }
      setEscalationMap(escMap);
    });
  }, [dispatchApi, ids]);

  useEffect(() => {
    if (ids.length < 1) {
      return;
    }
    dispatchApi(
      api.v2.search.facet.post(['hit', 'observable'], {
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

  const allAssets = useMemo(() => {
    if (!records || !_case) {
      return [];
    }

    const entries = buildAssetEntries(records);
    return entries.map(entry => ({
      ...entry,
      role: classifyRole(entry.value, _case, records),
      sources: resolveSources(entry.seenIn, _case.items, escalationMap)
    }));
  }, [records, _case, escalationMap]);

  const assetTypes = useMemo(
    () => (allAssets ? (uniq(allAssets.map(a => a.type)) as AssetType[]).sort() : []),
    [allAssets]
  );

  const filteredAssets = useMemo(() => {
    if (allAssets.length < 1) {
      return [];
    }

    let result = allAssets;

    if (activeFilters.size > 0) {
      result = result.filter(a => activeFilters.has(a.type));
    }

    if (searchQuery.trim()) {
      const query = searchQuery.trim().toLowerCase();
      result = result.filter(a => a.value.toLowerCase().includes(query) || a.type.toLowerCase().includes(query));
    }

    if (originFilters.size > 0) {
      result = result.filter(a => a.sources?.some(s => originFilters.has(s.type as OriginType)));
    }

    if (activeEscalations.size > 0) {
      result = result.filter(a => a.sources?.some(s => s.escalation && activeEscalations.has(s.escalation)));
    }

    if (roleFilters.size > 0) {
      result = result.filter(a => a.role && roleFilters.has(a.role));
    }

    return result;
  }, [allAssets, activeFilters, searchQuery, originFilters, activeEscalations, roleFilters]);

  const toggleSetItem = <T,>(setter: (updater: (prev: Set<T>) => Set<T>) => void, item: T) => {
    setter(prev => {
      const next = new Set(prev);
      if (next.has(item)) {
        next.delete(item);
      } else {
        next.add(item);
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
        <Stack spacing={1.5}>
          <TextField
            size="small"
            placeholder={t('page.cases.assets.search')}
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            sx={{ maxWidth: 360 }}
            id="asset-search"
          />
          <Stack direction="row" spacing={1} flexWrap="wrap">
            <ChipPopper
              icon={<FilterList />}
              label={
                activeFilters.size > 0
                  ? `${t('page.cases.assets.filter_by_type')} (${toArray(activeFilters)
                      .map(type => t(`page.cases.assets.type.${type}`))
                      .sort()
                      .join(', ')})`
                  : t('page.cases.assets.filter_by_type')
              }
              slotProps={{
                chip: { size: 'small', variant: 'outlined', color: activeFilters.size > 0 ? 'primary' : 'default' }
              }}
            >
              {records === null ? (
                <Skeleton width={200} height={32} />
              ) : (
                <Stack direction="row" gap={0.5} flexWrap="wrap">
                  {assetTypes.map(type => (
                    <Chip
                      key={type}
                      label={t(`page.cases.assets.type.${type}`)}
                      size="small"
                      onClick={() => toggleSetItem(setActiveFilters, type)}
                      color={activeFilters.has(type) ? 'primary' : 'default'}
                      variant={activeFilters.has(type) ? 'filled' : 'outlined'}
                    />
                  ))}
                </Stack>
              )}
            </ChipPopper>
            <ChipPopper
              icon={<FilterList />}
              label={
                originFilters.size > 0
                  ? `${t('page.cases.assets.filter_by_origin')} (${toArray(originFilters).join(', ')})`
                  : t('page.cases.assets.filter_by_origin')
              }
              slotProps={{
                chip: { size: 'small', variant: 'outlined', color: originFilters.size > 0 ? 'primary' : 'default' }
              }}
            >
              <Stack direction="row" gap={0.5} flexWrap="wrap">
                {(['hit', 'observable'] as OriginType[]).map(origin => (
                  <Chip
                    key={origin}
                    label={t(`page.cases.assets.origin.${origin}`)}
                    size="small"
                    onClick={() => toggleSetItem(setOriginFilters, origin)}
                    color={originFilters.has(origin) ? 'primary' : 'default'}
                    variant={originFilters.has(origin) ? 'filled' : 'outlined'}
                  />
                ))}
              </Stack>
            </ChipPopper>
            <ChipPopper
              icon={<FilterList />}
              label={
                roleFilters.size > 0
                  ? `${t('page.cases.assets.filter_by_role')} (${toArray(roleFilters).join(', ')})`
                  : t('page.cases.assets.filter_by_role')
              }
              slotProps={{
                chip: { size: 'small', variant: 'outlined', color: roleFilters.size > 0 ? 'primary' : 'default' }
              }}
            >
              <Stack direction="row" gap={0.5} flexWrap="wrap">
                {(['threat', 'target', 'indicator'] as AssetRole[]).map(role => (
                  <Chip
                    key={role}
                    label={t(`page.cases.assets.role.${role}`)}
                    size="small"
                    onClick={() => toggleSetItem(setRoleFilters, role)}
                    color={roleFilters.has(role) ? 'primary' : 'default'}
                    variant={roleFilters.has(role) ? 'filled' : 'outlined'}
                  />
                ))}
              </Stack>
            </ChipPopper>
            {escalationOptions.length > 0 && (
              <ChipPopper
                icon={<FilterList />}
                label={
                  activeEscalations.size > 0
                    ? `${t('page.cases.assets.filter_by_escalation')} (${toArray(activeEscalations).join(', ')})`
                    : t('page.cases.assets.filter_by_escalation')
                }
                slotProps={{
                  chip: {
                    size: 'small',
                    variant: 'outlined',
                    color: activeEscalations.size > 0 ? 'primary' : 'default'
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
                      color={activeEscalations.has(esc) ? 'primary' : 'default'}
                      variant={activeEscalations.has(esc) ? 'filled' : 'outlined'}
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
      ) : filteredAssets.length === 0 ? (
        <Grid item xs={12}>
          <Typography color="text.secondary">{t('page.cases.assets.empty')}</Typography>
        </Grid>
      ) : (
        <Grid item xs={12}>
          <AssetTable assets={filteredAssets} case={_case} />
        </Grid>
      )}
    </Grid>
  );
};

export default memo(CaseAssets);
