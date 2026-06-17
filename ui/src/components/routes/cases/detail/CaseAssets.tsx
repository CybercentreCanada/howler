import { FilterList } from '@mui/icons-material';
import { Chip, Grid, Skeleton, Stack, TextField, Typography } from '@mui/material';
import api from 'api';
import ChipPopper from 'components/elements/display/ChipPopper';
import useMyApi from 'components/hooks/useMyApi';
import { toArray, uniq } from 'lodash-es';
import type { Case } from 'models/entities/generated/Case';
import type { Hit } from 'models/entities/generated/Hit';
import type { Observable } from 'models/entities/generated/Observable';
import { memo, useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useOutletContext } from 'react-router-dom';
import useCase from '../hooks/useCase';
import AssetTable from './assets/AssetTable';
import type { AssetRole, AssetType } from './types';
import { ASSET_FIELDS, buildAssetEntries, classifyRole } from './utils';

const RELATED_FIELDS = ASSET_FIELDS.map(f => `related.${f}`).join(',');
const EXTRA_FIELDS =
  'howler.escalation,howler.outline.threat,howler.outline.target,howler.outline.indicators,threat.indicator.ip,threat.indicator.description';

const CaseAssets: FC<{ case?: Case; caseId?: string }> = ({ case: providedCase, caseId }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const routeCase = useOutletContext<Case>();
  const { case: _case } = useCase({ case: providedCase ?? routeCase, caseId });

  const [records, setRecords] = useState<Partial<Hit | Observable>[] | null>(null);
  const [activeFilters, setActiveFilters] = useState<AssetType[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [originFilters, setOriginFilters] = useState<OriginType[]>([]);
  const [roleFilters, setRoleFilters] = useState<AssetRole[]>([]);
  const [escalationOptions, setEscalationOptions] = useState<string[]>([]);
  const [activeEscalations, setActiveEscalations] = useState<string[]>([]);
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
      setEscalationOptions([]);
      setActiveEscalations([]);
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
  }, [allAssets, activeFilters, searchQuery, originFilters, activeEscalations, roleFilters]);

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
                activeFilters.length > 0
                  ? `${t('page.cases.assets.filter_by_type')} (${toArray(activeFilters)
                      .map(type => t(`page.cases.assets.type.${type}`))
                      .sort()
                      .join(', ')})`
                  : t('page.cases.assets.filter_by_type')
              }
              slotProps={{
                chip: { size: 'small', variant: 'outlined', color: activeFilters.length > 0 ? 'primary' : 'default' }
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
                  ? `${t('page.cases.assets.filter_by_origin')} (${toArray(originFilters).join(', ')})`
                  : t('page.cases.assets.filter_by_origin')
              }
              slotProps={{
                chip: { size: 'small', variant: 'outlined', color: originFilters.length > 0 ? 'primary' : 'default' }
              }}
            >
              <Stack direction="row" gap={0.5} flexWrap="wrap">
                {(['hit', 'observable'] as OriginType[]).map(origin => (
                  <Chip
                    key={origin}
                    label={t(`page.cases.assets.origin.${origin}`)}
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
                  ? `${t('page.cases.assets.filter_by_role')} (${toArray(roleFilters).join(', ')})`
                  : t('page.cases.assets.filter_by_role')
              }
              slotProps={{
                chip: { size: 'small', variant: 'outlined', color: roleFilters.length > 0 ? 'primary' : 'default' }
              }}
            >
              <Stack direction="row" gap={0.5} flexWrap="wrap">
                {(['threat', 'target', 'indicator'] as AssetRole[]).map(role => (
                  <Chip
                    key={role}
                    label={t(`page.cases.assets.role.${role}`)}
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
                    ? `${t('page.cases.assets.filter_by_escalation')} (${toArray(activeEscalations).join(', ')})`
                    : t('page.cases.assets.filter_by_escalation')
                }
                slotProps={{
                  chip: {
                    size: 'small',
                    variant: 'outlined',
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
