import { Topic } from '@mui/icons-material';
import { Stack, Typography } from '@mui/material';
import api from 'api';
import type { HowlerSearchResponse } from 'api/search';
import { TuiListProvider, type TuiListItem, type TuiListItemProps } from 'components/elements/addons/lists';
import { TuiListMethodContext, type TuiListMethodsState } from 'components/elements/addons/lists/TuiListProvider';
import ItemManager from 'components/elements/display/ItemManager';
import useMyApi from 'components/hooks/useMyApi';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import dayjs from 'dayjs';
import type { Case } from 'models/entities/generated/Case';
import { useCallback, useContext, useEffect, useRef, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { DATE_RANGE_LUCENE, StorageKey } from 'utils/constants';
import { sanitizeLuceneQuery } from 'utils/stringUtils';
import CaseCard from '../../elements/case/CaseCard';
import CaseAssigneeFilter from './search/CaseAssigneeFilter';
import CaseDateFilter, { type DateRangeOption } from './search/CaseDateFilter';
import CaseStatusFilter from './search/CaseStatusFilter';

const buildPhraseQuery = (phrase: string | null) => {
  const sanitized = sanitizeLuceneQuery(phrase);

  if (!phrase) {
    return '(title:* OR summary:* OR overview:* OR participants:* OR tasks.summary:* OR tasks.assignment:*)';
  }

  return (
    `(title:*${sanitized}* OR summary:*${sanitized}* OR overview:*${sanitized}* OR participants:*${sanitized}* ` +
    `OR tasks.summary:*${sanitized}* OR tasks.assignment:*${sanitized}*)`
  );
};

const CasesBase: FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { dispatchApi } = useMyApi();
  const [searchParams, setSearchParams] = useSearchParams();
  const { load } = useContext<TuiListMethodsState<Case>>(TuiListMethodContext);
  const pageCount = useMyLocalStorageItem(StorageKey.PAGE_COUNT, 25)[0];

  const [phrase, setPhrase] = useState<string>('');
  const [offset, setOffset] = useState(parseInt(searchParams.get('offset')) || 0);
  const [response, setResponse] = useState<HowlerSearchResponse<Case>>(null);
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
      setResponse(
        await dispatchApi(
          api.search.case.post({
            query: buildPhraseQuery(phrase),
            filters,
            rows: pageCount,
            offset
          })
        )
      );
    } catch (e) {
      setHasError(true);
    } finally {
      setLoading(false);
    }
  }, [buildFilters, phrase, setSearchParams, searchParams, dispatchApi, pageCount, offset]);

  // Load the items into list when response changes.
  useEffect(() => {
    if (response) {
      load(
        response.items.map((item: Case) => ({
          id: item.case_id,
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
    onSearch();

    if (!searchParams.has('offset')) {
      searchParams.set('offset', '0');
      setSearchParams(searchParams, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (response?.total <= offset) {
      setOffset(0);
      searchParams.set('offset', '0');
      setSearchParams(searchParams, { replace: true });
    }
  }, [offset, response?.total, searchParams, setSearchParams]);

  useEffect(() => {
    if (!loading) {
      onSearch();
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
      onSearch();
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
      onCreate={() => navigate('/cases/create')}
      createPrompt="route.cases.create"
      searchPrompt="route.cases.manager.search"
      createIcon={<Topic sx={{ mr: 1 }} />}
    />
  );
};

const Cases = () => {
  return (
    <TuiListProvider>
      <CasesBase />
    </TuiListProvider>
  );
};

export default Cases;
