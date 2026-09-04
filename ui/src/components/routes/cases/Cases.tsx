import { Topic } from '@mui/icons-material';
import { Stack, Typography } from '@mui/material';
import api from 'api';
import type { FuzzySearchItem } from 'api/v2/fuzzy';
import SearchResponseProvider, {
  createSearchResponseContext,
  useSearchResponseContext
} from 'components/app/providers/SearchResponseProvider';
import { TuiListProvider, type TuiListItem, type TuiListItemProps } from 'components/elements/addons/lists';
import { TuiListMethodContext, type TuiListMethodsState } from 'components/elements/addons/lists/TuiListProvider';
import ItemManager from 'components/elements/display/ItemManager';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import dayjs from 'dayjs';
import type { Case } from 'models/entities/generated/Case';
import { useCallback, useContext, useEffect, useRef, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router';
import { DATE_RANGE_LUCENE, StorageKey } from 'utils/constants';
import { sanitizeLuceneQuery } from 'utils/stringUtils';
import CaseCard from '../../elements/case/CaseCard';
import CaseAssigneeFilter from './search/CaseAssigneeFilter';
import CaseDateFilter, { type DateRangeOption } from './search/CaseDateFilter';
import CaseStatusFilter from './search/CaseStatusFilter';

const SearchResponseContext = createSearchResponseContext<FuzzySearchItem<Case>>();

const CasesBase: FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { load } = useContext<TuiListMethodsState<Case>>(TuiListMethodContext);
  const pageCount = useMyLocalStorageItem(StorageKey.PAGE_COUNT, 25)[0];

  const { response, request } = useSearchResponseContext(SearchResponseContext);

  const [phrase, setPhrase] = useState<string>('');
  const [offset, setOffset] = useState(parseInt(searchParams.get('offset') ?? '') || 0);
  const [hasError, setHasError] = useState(false);
  const [loading, setLoading] = useState(false);

  const [statusFilter, setStatusFilter] = useState<string[]>([]);
  const [assigneeFilter, setAssigneeFilter] = useState<string[]>([]);
  const [dateRange, setDateRange] = useState<DateRangeOption>('date.range.all');
  const [customStart, setCustomStart] = useState(dayjs().subtract(2, 'days'));
  const [customEnd, setCustomEnd] = useState(dayjs());

  const filtersReady = useRef(false);

  const buildFilters = useCallback((): string[] => {
    const filters: string[] = [];
    if (statusFilter.length > 0) {
      filters.push(`status:(${statusFilter.map(status => `"${status}"`).join(' OR ')})`);
    }

    if (assigneeFilter.length > 0) {
      filters.push(
        assigneeFilter
          .map(
            assignee =>
              `(participants:"${sanitizeLuceneQuery(assignee)}" OR tasks.assignment:"${sanitizeLuceneQuery(assignee)}")`
          )
          .join(' OR ')
      );
    }

    const lucene = DATE_RANGE_LUCENE[dateRange];
    if (lucene) {
      filters.push(`created:[${lucene} TO now]`);
    } else if (dateRange === 'date.range.custom') {
      filters.push(`created:[${customStart.toISOString()} TO ${customEnd.toISOString()}]`);
    }
    return filters;
  }, [statusFilter, assigneeFilter, dateRange, customStart, customEnd]);

  const onSearch = useCallback(async () => {
    try {
      setLoading(true);
      setHasError(false);

      if (phrase) {
        searchParams.set('phrase', phrase);
      } else {
        searchParams.delete('phrase');
      }
      setSearchParams(searchParams, { replace: true });

      const filters = buildFilters();
      await request(api.v2.fuzzy.post, {
        query: phrase.trim() || '*',
        filters,
        rows: pageCount,
        offset,
        indexes: ['case']
      });
    } catch {
      setHasError(true);
    } finally {
      setLoading(false);
    }
  }, [phrase, setSearchParams, searchParams, buildFilters, request, pageCount, offset]);

  // Load the items into list when response changes.
  useEffect(() => {
    if (response) {
      load(
        response.items.map(item => ({
          id: item.case_id!,
          item,
          selected: false,
          cursor: false
        }))
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [response, load]);

  const onPageChange = useCallback(
    (_offset: number) => {
      if (_offset !== offset) {
        searchParams.set('offset', _offset.toString());
        setSearchParams(searchParams, { replace: true });
        setOffset(_offset);
      }
    },
    [offset, searchParams, setSearchParams]
  );

  useEffect(() => {
    void onSearch();

    if (!searchParams.has('offset')) {
      searchParams.set('offset', '0');
      setSearchParams(searchParams, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if ((response?.total ?? 0) <= offset) {
      setOffset(0);
      searchParams.set('offset', '0');
      setSearchParams(searchParams, { replace: true });
    }
  }, [offset, response?.total, searchParams, setSearchParams]);

  useEffect(() => {
    if (!loading) {
      void onSearch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offset]);

  // Re-search when filter chips change, but skip the initial render.
  useEffect(() => {
    if (!filtersReady.current) {
      filtersReady.current = true;
      return;
    }
    if (!loading) {
      void onSearch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, assigneeFilter, dateRange, customStart, customEnd]);

  const renderer = useCallback((item: Case, className?: string) => <CaseCard case={item} className={className} />, []);

  return (
    <ItemManager
      onSearch={onSearch}
      onPageChange={onPageChange}
      phrase={phrase}
      setPhrase={setPhrase}
      hasError={hasError}
      searching={loading}
      aboveSearch={
        <Typography
          sx={theme => ({ fontStyle: 'italic', color: theme.palette.text.disabled, mb: 0.5 })}
          variant="body2"
        >
          {t('route.cases.search.prompt')}
        </Typography>
      }
      searchFilters={
        <Stack direction="row" spacing={1} useFlexGap sx={{ mt: 0.5, flexWrap: 'wrap' }}>
          <CaseStatusFilter statusFilter={statusFilter} onChange={setStatusFilter} />
          <CaseAssigneeFilter assigneeFilter={assigneeFilter} onChange={setAssigneeFilter} />
          <CaseDateFilter
            dateRange={dateRange}
            onChange={setDateRange}
            customStart={customStart}
            customEnd={customEnd}
            onCustomStartChange={setCustomStart}
            onCustomEndChange={setCustomEnd}
          />
        </Stack>
      }
      renderer={({ item }: TuiListItemProps<Case>, classRenderer) => renderer(item.item, classRenderer())}
      response={response}
      onSelect={(item: TuiListItem<Case>) => navigate(`/cases/${item.id}`)}
      searchPrompt="route.cases.manager.search"
      createIcon={<Topic sx={{ mr: 1 }} />}
    />
  );
};

const Cases = () => {
  return (
    <TuiListProvider>
      <SearchResponseProvider context={SearchResponseContext} idField="case_id">
        <CasesBase />
      </SearchResponseProvider>
    </TuiListProvider>
  );
};

export default Cases;
