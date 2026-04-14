import { FilterList } from '@mui/icons-material';
import { Autocomplete, Box, Chip, Divider, Skeleton, Stack, TextField, Tooltip, Typography } from '@mui/material';
import api from 'api';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { RecordContext } from 'components/app/providers/RecordProvider';
import HitCard from 'components/elements/hit/HitCard';
import { HitLayout } from 'components/elements/hit/HitLayout';
import ObservableCard from 'components/elements/observable/ObservableCard';
import useMyApi from 'components/hooks/useMyApi';
import dayjs from 'dayjs';
import { capitalize } from 'lodash-es';
import type { Case } from 'models/entities/generated/Case';
import type { Hit } from 'models/entities/generated/Hit';
import type { Observable } from 'models/entities/generated/Observable';
import { memo, useContext, useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useOutletContext } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import { ESCALATION_COLORS } from 'utils/constants';
import { isHit } from 'utils/typeUtils';
import useCase from '../hooks/useCase';

interface MitreOption {
  id: string;
  name: string;
  kind: 'tactic' | 'technique';
}

// builds the additional filters for the lucene query
export const buildFilters = (mitre: MitreOption[], escalations: string[]): string[] => {
  const filters: string[] = [];

  const tacticIds = mitre.filter(o => o.kind === 'tactic').map(o => o.id);
  const techniqueIds = mitre.filter(o => o.kind === 'technique').map(o => o.id);

  if (tacticIds.length) {
    filters.push(`threat.tactic.id:(${tacticIds.join(' OR ')})`);
  }

  if (techniqueIds.length) {
    filters.push(`threat.technique.id:(${techniqueIds.join(' OR ')})`);
  }

  if (escalations.length) {
    filters.push(`howler.escalation:(${escalations.join(' OR ')})`);
  }

  return filters;
};

const CaseTimeline: FC<{ case?: Case; caseId?: string }> = ({ case: providedCase, caseId }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const { config } = useContext(ApiConfigContext);
  const routeCase = useOutletContext<Case>();
  const { case: _case } = useCase({ case: providedCase ?? routeCase, caseId });
  const loadRecords = useContextSelector(RecordContext, ctx => ctx.loadRecords);

  const [mitreOptions, setMitreOptions] = useState<MitreOption[]>([]);
  const [escalationOptions, setEscalationOptions] = useState<string[]>([]);
  const [displayedEntries, setDisplayedEntries] = useState<(Hit | Observable)[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedMitres, setSelectedMitres] = useState<MitreOption[]>([]);
  const [selectedEscalations, setSelectedEscalations] = useState<string[]>(['evidence']);

  const ids = useMemo(
    () =>
      (_case?.items ?? [])
        .filter(item => ['hit', 'observable'].includes(item.type))
        .map(item => item.value)
        .filter(Boolean),
    [_case]
  );

  const getPath = (value: string) => _case!.items.find(item => item.value === value)?.path;

  useEffect(() => {
    if (ids.length < 1) {
      return;
    }

    dispatchApi(
      api.v2.search.facet.post(['hit', 'observable'], {
        fields: ['threat.tactic.id', 'threat.technique.id', 'howler.escalation'],
        filters: [`howler.id:(${ids.join(' OR ')})`]
      }),
      { throwError: false }
    ).then(result => {
      if (!result) {
        return;
      }

      setEscalationOptions(Object.keys(result['howler.escalation'] ?? {}) as string[]);

      const tactics: MitreOption[] = Object.keys(result['threat.tactic.id'] ?? {}).map(tactic => ({
        id: tactic,
        name: config.lookups?.tactics?.[tactic].name ?? tactic,
        kind: 'tactic'
      }));

      const techniques: MitreOption[] = Object.keys(result['threat.technique.id'] ?? {}).map(technique => ({
        id: technique,
        name: config.lookups?.techniques?.[technique].name ?? technique,
        kind: 'technique'
      }));

      setMitreOptions([...tactics, ...techniques]);
    });
  }, [config.lookups?.tactics, config.lookups?.techniques, dispatchApi, ids]);

  useEffect(() => {
    if (!ids.length) {
      setDisplayedEntries([]);
      return;
    }

    setLoading(true);

    const filters = buildFilters(selectedMitres, selectedEscalations);

    dispatchApi(
      api.v2.search.post<Hit | Observable>(['hit', 'observable'], {
        query: `howler.id:(${ids.join(' OR ')})`,
        sort: 'event.created asc',
        rows: ids.length,
        filters
      }),
      { throwError: false }
    ).then(response => {
      setLoading(false);

      if (!response) {
        return;
      }

      loadRecords(response.items);
      setDisplayedEntries(response.items);
    });
  }, [ids, selectedMitres, selectedEscalations, dispatchApi, loadRecords]);

  if (!_case) {
    return null;
  }

  return (
    <Stack spacing={0} sx={{ height: '100%' }}>
      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" sx={{ p: 1, gap: 1 }}>
        <Tooltip title={t('page.cases.timeline.filter.label')}>
          <FilterList fontSize="small" color="action" />
        </Tooltip>

        <Autocomplete
          multiple
          size="small"
          options={mitreOptions}
          value={selectedMitres}
          onChange={(_e, values) => setSelectedMitres(values)}
          getOptionLabel={opt => `${opt.id} - ${opt.name}`}
          isOptionEqualToValue={(opt, val) => opt.id === val.id}
          groupBy={opt => capitalize(opt.kind)}
          renderTags={(value, getTagProps) =>
            value.map((opt, index) => (
              <Chip {...getTagProps({ index })} key={opt.id} size="small" label={opt.id} color="primary" />
            ))
          }
          renderInput={params => (
            <TextField {...params} label={t('page.cases.timeline.filter.mitre')} sx={{ minWidth: 260 }} />
          )}
          noOptionsText={t('page.cases.timeline.filter.mitre.empty')}
        />
        <Autocomplete
          multiple
          size="small"
          options={escalationOptions}
          value={selectedEscalations}
          onChange={(_e, value) => setSelectedEscalations(value)}
          getOptionLabel={opt => t(`howler.escalation.${opt}`, opt)}
          renderTags={(value, getTagProps) =>
            value.map((opt, index) => (
              <Chip {...getTagProps({ index })} key={opt} size="small" label={opt} color={ESCALATION_COLORS[opt]} />
            ))
          }
          renderInput={params => (
            <TextField {...params} label={t('page.cases.timeline.filter.escalation')} sx={{ minWidth: 220 }} />
          )}
          noOptionsText={t('page.cases.timeline.filter.escalation.empty')}
        />
      </Stack>
      <Divider />
      {loading ? (
        <Stack spacing={2} sx={{ px: 2, py: 1 }}>
          {[0, 1, 2].map(i => (
            <Stack key={i} direction="row" width="100%" spacing={1}>
              <Skeleton variant="text" width={120} height={24} />

              <Skeleton variant="rounded" height={120} sx={{ flex: 1 }} />
            </Stack>
          ))}
        </Stack>
      ) : displayedEntries.length === 0 ? (
        <Box sx={{ pt: 4, textAlign: 'center' }}>
          <Typography color="textSecondary">{t('page.cases.timeline.empty')}</Typography>
        </Box>
      ) : (
        <Stack component="ol" spacing={0} sx={{ px: 2, py: 1, listStyle: 'none', m: 0, overflow: 'auto' }}>
          {displayedEntries.map(entry => (
            <Stack component="li" spacing={1} key={entry.howler.id} sx={{ pb: 1 }}>
              <Stack direction="row" spacing={2} alignItems="flex-start">
                <Stack spacing={0.5} alignItems="end">
                  <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>
                    {dayjs(entry.event?.created ?? entry.timestamp).format('YYYY-MM-DD HH:mm:ss')}
                  </Typography>
                  {entry.threat?.technique?.id && (
                    <Typography
                      component="a"
                      href={`https://attack.mitre.org/techniques/${entry.threat.technique.id}`}
                      variant="caption"
                      color="text.secondary"
                      sx={{ whiteSpace: 'nowrap' }}
                    >
                      {entry.threat.technique.id}
                    </Typography>
                  )}

                  {entry.threat?.tactic?.id && (
                    <Typography
                      component="a"
                      href={`https://attack.mitre.org/tactics/${entry.threat.tactic.id}`}
                      variant="caption"
                      color="text.secondary"
                      sx={{ whiteSpace: 'nowrap' }}
                    >
                      {entry.threat.tactic.id}
                    </Typography>
                  )}
                </Stack>
                <Box
                  component={Link}
                  to={`/cases/${_case.case_id}/${getPath(entry.howler.id)}`}
                  sx={{ flex: 1, minWidth: 0, textDecoration: 'none' }}
                >
                  {isHit(entry) ? (
                    <HitCard id={entry.howler.id} layout={HitLayout.DENSE} readOnly />
                  ) : (
                    <ObservableCard id={entry.howler.id} />
                  )}
                </Box>
              </Stack>
              <Divider flexItem />
            </Stack>
          ))}
        </Stack>
      )}
    </Stack>
  );
};

export default memo(CaseTimeline);
