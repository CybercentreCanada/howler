import { OpenInNew } from '@mui/icons-material';
import { Card, CardContent, IconButton, Skeleton, Stack, Typography } from '@mui/material';
import { AppListEmpty } from '@tui/core';
import api from 'api';
import type { SearchIndex } from 'api/v2/search';
import type { RecordContextType } from 'components/app/providers/RecordProvider';
import { useRecordContextSelector } from 'components/app/providers/RecordProvider';
import { ViewContext } from 'components/app/providers/ViewProvider';
import EventCard from 'components/elements/event/EventCard';
import HitBanner from 'components/elements/hit/HitBanner';
import { HitLayout } from 'components/elements/hit/HitLayout';
import RecordContextMenu from 'components/elements/record/RecordContextMenu';
import useMyApi from 'components/hooks/useMyApi';
import type { Event } from 'models/entities/generated/Event';
import type { Hit } from 'models/entities/generated/Hit';
import { useCallback, useEffect, useMemo, useRef, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router';
import { useContextSelector } from 'use-context-selector';
import { isEvent } from 'utils/typeUtils';
import { convertDateToLucene } from 'utils/utils';
import { buildViewUrl } from 'utils/viewUtils';

// Custom hook to select records by IDs with proper memoization
const useSelectRecordsByIds = (recordIds: string[]): (Hit | Event)[] => {
  const recordIdsRef = useRef<string[]>(recordIds);
  const prevResultRef = useRef<(Hit | Event)[]>([]);
  const prevRecordIdsRef = useRef<string[]>([]);

  // Keep ref up to date with latest recordIds
  recordIdsRef.current = recordIds;

  const selector = useCallback((ctx: RecordContextType) => {
    const currentRecordIds = recordIdsRef.current;

    // Fast path: if recordIds array didn't change, check if record objects changed
    if (
      prevRecordIdsRef.current.length === currentRecordIds.length &&
      currentRecordIds.every((id, i) => id === prevRecordIdsRef.current[i])
    ) {
      // RecordIds unchanged - check if any record objects changed by reference
      const anyRecordChanged = currentRecordIds.some((id, i) => ctx.records[id] !== prevResultRef.current[i]);
      if (!anyRecordChanged) {
        return prevResultRef.current;
      }
    }

    // Something changed - rebuild the array
    const currentRecords = currentRecordIds.map(id => ctx.records[id]).filter(Boolean);
    prevRecordIdsRef.current = currentRecordIds;
    prevResultRef.current = currentRecords;
    return currentRecords;
  }, []); // Empty deps - selector never changes

  return useRecordContextSelector(selector);
};

// Utility functions
const normalize = (val: any) => (val == null ? '' : String(val));

// Have to normalize the fields as websockets and api return null and undefined respectively. This causes false positives when comparing signatures if not normalized to a consistent value. We also stringify non-primitive values to ensure changes are detected.
const createRecordSignature = (record: Hit | Event) => {
  if (!record) {
    return '';
  }

  if (isEvent(record)) {
    return record.howler?.id;
  }

  return `${record.howler?.id}:${normalize(record.howler?.status)}:${normalize(record.howler?.assignment)}:${normalize(record.howler?.assessment)}`;
};

const createSignatureFromRecords = (records: (Hit | Event)[]) => {
  if (records.length === 0) {
    return '';
  }
  return records.map(createRecordSignature).join('|');
};

const DEBOUNCE_TIME = 1000; // 1 second debounce for signature changes

export interface ViewSettings {
  viewId: string;
  limit: number;
  panelId?: string;
  refreshTick?: symbol;
  onRefreshComplete?: (panelId: string, refreshTick: symbol) => void;
}

const ViewCard: FC<ViewSettings> = ({
  viewId,
  limit,
  panelId = viewId,
  refreshTick,
  onRefreshComplete
}: ViewSettings) => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();

  const [recordIds, setRecordIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [signatureRefresh, setSignatureRefresh] = useState(0);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeRefreshTick = useRef<symbol | undefined>(undefined);
  const lastSignature = useRef<string>('');

  const view = useContextSelector(ViewContext, ctx => ctx.views[viewId]);
  const fetchViews = useContextSelector(ViewContext, ctx => ctx.fetchViews);
  const loadRecords = useRecordContextSelector(ctx => ctx.loadRecords);

  // Subscribe to hits from HitProvider cache based on current hitIds in the view
  // Uses memoized selector to avoid unnecessary re-renders on unrelated hit updates
  const records = useSelectRecordsByIds(recordIds);

  // Create a stable signature that only changes when relevant fields change
  const recordsSignature = useMemo(() => createSignatureFromRecords(records), [records]);

  const debouncedRefresh = useCallback(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    debounceTimerRef.current = setTimeout(() => {
      setSignatureRefresh(previous => previous + 1);
    }, DEBOUNCE_TIME);
  }, []);

  useEffect(() => {
    void fetchViews([viewId]);
  }, [fetchViews, viewId]);

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

    if (!view?.query) {
      completeRefresh();
      return () => controller.abort();
    }

    const loadingTimeout = setTimeout(() => setLoading(true), 200);
    const query = view.query;
    const indexes = view.indexes;
    const sort = view.sort;
    const span = view.span;

    void dispatchApi(
      api.v2.search.post<Hit | Event>(
        (indexes ?? ['hit']) as SearchIndex[],
        {
          query,
          rows: limit,
          sort,
          filters: span ? [`event.created:${convertDateToLucene(span)}`] : [],
          metadata: ['analytic']
        },
        controller.signal
      )
    )
      .then(response => {
        if (controller.signal.aborted || !response) {
          return;
        }

        const fetchedRecords = response.items ?? [];
        loadRecords(fetchedRecords);
        setRecordIds(fetchedRecords.map(record => record.howler.id));
        lastSignature.current = createSignatureFromRecords(fetchedRecords);
      })
      .catch(() => {
        // Aborted requests are expected when newer view inputs supersede this search.
      })
      .finally(() => {
        clearTimeout(loadingTimeout);
        if (!controller.signal.aborted) {
          setLoading(false);
          completeRefresh();
        }
      });

    return () => {
      controller.abort();
      clearTimeout(loadingTimeout);
    };
  }, [dispatchApi, limit, loadRecords, onRefreshComplete, panelId, refreshTick, signatureRefresh, view]);

  // Monitor hits currently in the view for changes that might affect query results
  useEffect(() => {
    if (!recordsSignature || recordIds.length === 0 || !lastSignature.current) {
      lastSignature.current = recordsSignature;
      return;
    }

    // Check if signature actually changed
    if (lastSignature.current === recordsSignature) {
      return;
    }

    debouncedRefresh();
  }, [recordsSignature, recordIds, debouncedRefresh]);

  useEffect(
    () => () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }

      if (activeRefreshTick.current) {
        onRefreshComplete?.(panelId, activeRefreshTick.current);
        activeRefreshTick.current = undefined;
      }
    },
    [onRefreshComplete, panelId]
  );

  const onClick = useCallback((query: string) => navigate('/hits?query=' + query), [navigate]);

  const getSelectedId = useCallback((event: React.MouseEvent<HTMLDivElement, MouseEvent>) => {
    const target = event.target as HTMLElement;
    const selectedElement = target.closest('[id]') as HTMLElement;

    if (!selectedElement) {
      return '';
    }

    return selectedElement.id;
  }, []);

  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <Stack spacing={1} sx={{ p: 1, minHeight: 100 }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="h6">
            {t(view?.title ?? '') || <Skeleton variant="text" height="2em" width="100px" />}
          </Typography>
          <IconButton
            size="small"
            component={Link}
            disabled={!view}
            to={view ? buildViewUrl(view) : ''}
            onClick={() => onClick(view!.query!)}
          >
            <OpenInNew fontSize="small" />
          </IconButton>
        </Stack>
        {loading ? (
          <>
            <Skeleton height={150} width="100%" variant="rounded" />
            <Skeleton height={160} width="100%" variant="rounded" />
            <Skeleton height={140} width="100%" variant="rounded" />
          </>
        ) : records.length > 0 ? (
          <RecordContextMenu getSelectedId={getSelectedId}>
            {records.map((r: Event | Hit) => (
              <Card
                id={r.howler.id}
                variant="outlined"
                key={r.howler.id}
                sx={{ cursor: 'pointer' }}
                onClick={() => navigate(`/hits/${r.howler.id}`)}
              >
                <CardContent>
                  {r.__index == 'hit' ? (
                    <HitBanner layout={HitLayout.DENSE} hit={r} />
                  ) : (
                    <EventCard event={r}></EventCard>
                  )}
                </CardContent>
              </Card>
            ))}
          </RecordContextMenu>
        ) : (
          <AppListEmpty />
        )}
      </Stack>
    </Card>
  );
};

export default ViewCard;
