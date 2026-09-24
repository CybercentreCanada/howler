import { OpenInNew } from '@mui/icons-material';
import { Alert, Card, CardContent, CircularProgress, IconButton, Stack, Tooltip, Typography } from '@mui/material';
import { AppListEmpty } from '@tui/core';
import api from 'api';
import CaseCard from 'components/elements/case/CaseCard';
import useMyApi from 'components/hooks/useMyApi';
import CaseAssigneeFilter from 'components/routes/cases/search/CaseAssigneeFilter';
import CaseDateFilter, { type DateRangeOption } from 'components/routes/cases/search/CaseDateFilter';
import CaseStatusFilter from 'components/routes/cases/search/CaseStatusFilter';
import dayjs, { type Dayjs } from 'dayjs';
import type { Case } from 'models/entities/generated/Case';
import { useEffect, useMemo, useRef, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { DATE_RANGE_LUCENE } from 'utils/constants';
import { sanitizeLuceneQuery } from 'utils/stringUtils';

const CASE_LIMIT = 10;

export interface CaseSettings {
  statusFilter?: string[];
  assigneeFilter?: string[];
  dateRange?: DateRangeOption;
  customStart?: string;
  customEnd?: string;
}

interface CasePanelProps extends CaseSettings {
  panelId?: string;
  refreshTick?: symbol;
  onRefreshComplete?: (panelId: string, refreshTick: symbol) => void;
}

const getDate = (value: string | undefined, fallback: Dayjs) => {
  const date = value ? dayjs(value) : fallback;
  return date.isValid() ? date : fallback;
};

const CasePanel: FC<CasePanelProps> = ({
  statusFilter: initialStatusFilter = [],
  assigneeFilter: initialAssigneeFilter = [],
  dateRange: initialDateRange = 'date.range.all',
  customStart: initialCustomStart,
  customEnd: initialCustomEnd,
  panelId = 'case-panel',
  refreshTick,
  onRefreshComplete
}) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();

  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [statusFilter, setStatusFilter] = useState(initialStatusFilter);
  const [assigneeFilter, setAssigneeFilter] = useState(initialAssigneeFilter);
  const [dateRange, setDateRange] = useState<DateRangeOption>(initialDateRange);
  const [customStart, setCustomStart] = useState(() => getDate(initialCustomStart, dayjs().subtract(2, 'days')));
  const [customEnd, setCustomEnd] = useState(() => getDate(initialCustomEnd, dayjs()));
  const activeRefreshTick = useRef<symbol | undefined>(undefined);
  const filters = useMemo(() => {
    const nextFilters: string[] = [];

    if (statusFilter.length > 0) {
      nextFilters.push(`status:(${statusFilter.map(status => `"${status}"`).join(' OR ')})`);
    }

    if (assigneeFilter.length > 0) {
      nextFilters.push(
        assigneeFilter
          .map(
            assignee =>
              `(participants:"${sanitizeLuceneQuery(assignee)}" OR tasks.assignment:"${sanitizeLuceneQuery(assignee)}")`
          )
          .join(' OR ')
      );
    }

    const luceneDate = DATE_RANGE_LUCENE[dateRange];
    if (luceneDate) {
      nextFilters.push(`created:[${luceneDate} TO now]`);
    } else if (dateRange === 'date.range.custom') {
      nextFilters.push(`created:[${customStart.toISOString()} TO ${customEnd.toISOString()}]`);
    }

    return nextFilters;
  }, [assigneeFilter, customEnd, customStart, dateRange, statusFilter]);

  useEffect(() => {
    const controller = new AbortController();
    let refreshComplete = false;
    const completeRefresh = () => {
      if (refreshTick && !refreshComplete) {
        refreshComplete = true;
        if (activeRefreshTick.current === refreshTick) {
          activeRefreshTick.current = undefined;
        }
        onRefreshComplete?.(panelId, refreshTick);
      }
    };

    if (refreshTick) {
      activeRefreshTick.current = refreshTick;
    }

    setLoading(true);
    setError(false);

    void dispatchApi(
      api.v2.search.post<Case>(
        'case',
        {
          query: 'case_id:*',
          filters,
          rows: CASE_LIMIT,
          sort: 'created desc'
        },
        controller.signal
      ),
      { showError: false }
    )
      .then(response => {
        if (!controller.signal.aborted) {
          setCases(response?.items ?? []);
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setError(true);
          setCases([]);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
          completeRefresh();
        }
      });

    return () => {
      controller.abort();
    };
  }, [dispatchApi, filters, onRefreshComplete, panelId, refreshTick]);

  useEffect(
    () => () => {
      if (activeRefreshTick.current) {
        onRefreshComplete?.(panelId, activeRefreshTick.current);
        activeRefreshTick.current = undefined;
      }
    },
    [onRefreshComplete, panelId]
  );

  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardContent sx={{ height: '100%' }}>
        <Stack spacing={1}>
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="h6">{t('route.home.case.title')}</Typography>
            <Tooltip title={t('route.home.case.open')}>
              <IconButton component={Link} to="/cases">
                <OpenInNew fontSize="small" />
              </IconButton>
            </Tooltip>
          </Stack>
          <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
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
          {error ? (
            <Alert severity="error">{t('route.home.case.error')}</Alert>
          ) : loading ? (
            <Stack alignItems="center" py={3}>
              <CircularProgress size={28} />
            </Stack>
          ) : cases.length > 0 ? (
            cases.map(_case => (
              <Link
                key={_case.case_id}
                to={`/cases/${_case.case_id}`}
                style={{ color: 'inherit', textDecoration: 'none' }}
              >
                <CaseCard case={_case} />
              </Link>
            ))
          ) : (
            <AppListEmpty />
          )}
        </Stack>
      </CardContent>
    </Card>
  );
};

export default CasePanel;
