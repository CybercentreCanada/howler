import { Box, Skeleton, Stack, Typography } from '@mui/material';
import api from 'api';
import type { HowlerSearchResponse } from 'api/search';
import type { FuzzySearchItem } from 'api/v2/fuzzy';
import PageCenter from 'commons/components/pages/PageCenter';
import ParameterProvider, { ParameterContext } from 'components/app/providers/ParameterProvider';
import SearchPagination from 'components/elements/addons/search/SearchPagination';
import SearchTotal from 'components/elements/addons/search/SearchTotal';
import CaseCard from 'components/elements/case/CaseCard';
import HitCard from 'components/elements/hit/HitCard';
import { HitLayout } from 'components/elements/hit/HitLayout';
import ObservableCard from 'components/elements/observable/ObservableCard';
import FuzzySearchBar from 'components/elements/search/FuzzySearchBar';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import type { Case } from 'models/entities/generated/Case';
import type { FC } from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import { StorageKey } from 'utils/constants';
import { isCase, isHit, isObservable } from 'utils/typeUtils';

const CaseSearch: FC = () => {
  const parentCase = useOutletContext<Case>();

  const indexes = useContextSelector(ParameterContext, ctx => ctx.indexes);
  const query = useContextSelector(ParameterContext, ctx => ctx.query);

  const [hitLayout] = useMyLocalStorageItem(StorageKey.HIT_LAYOUT, HitLayout.NORMAL);

  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<HowlerSearchResponse<FuzzySearchItem> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);

  const caseIds = useMemo(
    () =>
      parentCase
        ? [parentCase.case_id, ...parentCase.items.filter(item => item.type === 'case').map(item => item.value)]
        : [],
    [parentCase]
  );

  const handleSearch = useCallback(
    async (_query: string, _indexes: string[]) => {
      setLoading(true);
      setError(null);

      try {
        // If no indexes specified, search across all types
        const searchIndexes = _indexes.length > 0 ? _indexes : ['case', 'hit', 'observable'];

        // Add case_id to the filters to scope the search to this case and its sub-cases
        const filters = parentCase?.case_id
          ? [`case_id:(${caseIds.join(' OR ')}) OR howler.related:${caseIds.join(' OR ')}`]
          : [];

        setResponse(
          await api.v2.fuzzy.post({
            query: _query,
            indexes: searchIndexes,
            rows: 25,
            filters,
            offset
          })
        );
      } catch (err: any) {
        setError(err.message || 'An error occurred while searching.');
        setResponse(null);
      } finally {
        setLoading(false);
      }
    },
    [caseIds, offset, parentCase?.case_id]
  );

  useEffect(() => {
    if (query) {
      handleSearch(query, indexes);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [indexes, offset]);

  return (
    <ParameterProvider defaults={{ query: '', indexes: ['hit', 'observable', 'case'] }}>
      <PageCenter maxWidth="lg" textAlign="left">
        <Stack spacing={1}>
          <FuzzySearchBar onSearch={handleSearch} loading={loading} />

          {response && (
            <Stack direction="row" alignItems="center" sx={{ pt: 1 }}>
              <SearchTotal
                total={response.total}
                pageLength={response.items.length}
                offset={response.offset}
                sx={theme => ({ color: theme.palette.text.secondary, fontSize: '0.9em', fontStyle: 'italic' })}
              />
              <Box flex={1} />
              <SearchPagination
                total={response.total}
                limit={response.rows}
                offset={response.offset}
                onChange={nextOffset => setOffset(nextOffset)}
              />
            </Stack>
          )}
          {error && (
            <Typography color="error" sx={{ mb: 2 }}>
              {error}
            </Typography>
          )}
          {loading ? (
            <>
              <Skeleton variant="rounded" height={430} />
            </>
          ) : (
            (response?.items ?? []).map(item => {
              if (isHit(item)) {
                return <HitCard key={item.howler.id} id={item.howler.id} layout={hitLayout} />;
              } else if (isObservable(item)) {
                return <ObservableCard key={item.howler.id} id={item.howler.id} observable={item} />;
              } else if (isCase(item)) {
                return <CaseCard key={item.case_id} caseId={item.case_id} case={item} />;
              }
            })
          )}
        </Stack>
      </PageCenter>
    </ParameterProvider>
  );
};

export default CaseSearch;
