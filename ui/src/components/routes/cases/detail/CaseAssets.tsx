import { Chip, Grid, Skeleton, Stack, Typography } from '@mui/material';
import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import type { Case } from 'models/entities/generated/Case';
import type { Hit } from 'models/entities/generated/Hit';
import type { Observable } from 'models/entities/generated/Observable';
import type { Related } from 'models/entities/generated/Related';
import { useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useOutletContext } from 'react-router-dom';
import useCase from '../hooks/useCase';
import Asset, { type AssetEntry, type AssetType } from './assets/Asset';

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

const CaseAssets: FC<{ case?: Case; caseId?: string }> = ({ case: providedCase, caseId }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const routeCase = useOutletContext<Case>();
  const { case: _case } = useCase({ case: providedCase ?? routeCase, caseId });

  const [records, setRecords] = useState<Partial<Hit | Observable>[] | null>(null);
  const [activeFilters, setActiveFilters] = useState<Set<AssetType>>(new Set());

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
        fl: `howler.id,${RELATED_FIELDS}`
      })
    ).then(response => setRecords(response.items));
  }, [dispatchApi, ids]);

  const allAssets = useMemo(() => (records ? buildAssetEntries(records) : []), [records]);

  const assetTypes = useMemo(
    () => (allAssets ? ([...new Set(allAssets.map(a => a.type))] as AssetType[]).sort() : []),
    [allAssets]
  );

  const filteredAssets = useMemo(() => {
    if (allAssets.length < 1) {
      return [];
    }

    if (activeFilters.size === 0) {
      return allAssets;
    }

    return allAssets.filter(a => activeFilters.has(a.type));
  }, [allAssets, activeFilters]);

  const toggleFilter = (type: AssetType) => {
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
            {t('page.cases.assets.filter_by_type')}
          </Typography>
          {records === null ? (
            <Skeleton width={240} height={32} />
          ) : (
            assetTypes.map(type => (
              <Chip
                key={type}
                label={t(`page.cases.assets.type.${type}`)}
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
      ) : filteredAssets.length === 0 ? (
        <Grid item xs={12}>
          <Typography color="text.secondary">{t('page.cases.assets.empty')}</Typography>
        </Grid>
      ) : (
        filteredAssets.map(asset => (
          <Grid key={`${asset.type}:${asset.value}`} item xs={12} md={6} xl={4}>
            <Asset asset={asset} case={_case} />
          </Grid>
        ))
      )}
    </Grid>
  );
};

export default CaseAssets;
