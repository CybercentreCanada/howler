import { OpenInNew } from '@mui/icons-material';
import { Card, CardContent, IconButton, Skeleton, Stack, Typography } from '@mui/material';
import api from 'api';
import AppListEmpty from 'commons/components/display/AppListEmpty';
import { useHitContextSelector } from 'components/app/providers/HitProvider';
import { ViewContext } from 'components/app/providers/ViewProvider';
import HitBanner from 'components/elements/hit/HitBanner';
import { HitLayout } from 'components/elements/hit/HitLayout';
import useMyApi from 'components/hooks/useMyApi';
import HitContextMenu from 'components/routes/hits/search/HitContextMenu';
import type { Hit } from 'models/entities/generated/Hit';
import { useCallback, useEffect, useMemo, useRef, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import { buildViewUrl } from 'utils/viewUtils';

// Custom hook to select hits by IDs with proper memoization
const useSelectHitsByIds = (hitIds: string[]) => {
  const hitIdsRef = useRef<string[]>(hitIds);
  const prevResultRef = useRef<Hit[]>([]);
  const prevHitIdsRef = useRef<string[]>([]);

  // Keep ref up to date with latest hitIds
  hitIdsRef.current = hitIds;

  const selector = useCallback(ctx => {
    const currentHitIds = hitIdsRef.current;

    // Fast path: if hitIds array didn't change, check if hit objects changed
    if (
      prevHitIdsRef.current.length === currentHitIds.length &&
      currentHitIds.every((id, i) => id === prevHitIdsRef.current[i])
    ) {
      // HitIds unchanged - check if any hit objects changed by reference
      const anyHitChanged = currentHitIds.some((id, i) => ctx.hits[id] !== prevResultRef.current[i]);
      if (!anyHitChanged) {
        return prevResultRef.current;
      }
    }

    // Something changed - rebuild the array
    const currentHits = currentHitIds.map(id => ctx.hits[id]).filter(Boolean);
    prevHitIdsRef.current = currentHitIds;
    prevResultRef.current = currentHits;
    return currentHits;
  }, []); // Empty deps - selector never changes

  return useHitContextSelector(selector);
};

// Utility functions
const normalize = (val: any) => (val == null ? '' : String(val));

// Have to normalize the fields as websockets and api return null and undefined respectively. This causes false positives when comparing signatures if not normalized to a consistent value. We also stringify non-primitive values to ensure changes are detected.
const createHitSignature = (hit: Hit) => {
  if (!hit) return '';
  return `${hit.howler?.id}:${normalize(hit.howler?.status)}:${normalize(hit.howler?.assignment)}:${normalize(hit.howler?.assessment)}`;
};

const createSignatureFromHits = (hits: Hit[]) => {
  if (hits.length === 0) return '';
  return hits.map(createHitSignature).join('|');
};

const DEBOUNCE_TIME = 1000; // 1 second debounce for signature changes

export interface ViewSettings {
  viewId: string;
  limit: number;
  refreshTick?: symbol;
  onRefreshComplete?: () => void;
}

const ViewCard: FC<ViewSettings> = ({ viewId, limit, refreshTick, onRefreshComplete }: ViewSettings) => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();

  const [hitIds, setHitIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isRefreshing = useRef(false);
  const lastSignature = useRef<string>('');

  const view = useContextSelector(ViewContext, ctx => ctx.views[viewId]);
  const fetchViews = useContextSelector(ViewContext, ctx => ctx.fetchViews);
  const loadHits = useHitContextSelector(ctx => ctx.loadHits);

  // Subscribe to hits from HitProvider cache based on current hitIds in the view
  // Uses memoized selector to avoid unnecessary re-renders on unrelated hit updates
  const hits = useSelectHitsByIds(hitIds);

  // Create a stable signature that only changes when relevant fields change
  const hitsSignature = useMemo(() => createSignatureFromHits(hits), [hits]);

  const refreshView = useCallback(async () => {
    if (!view?.query || isRefreshing.current) {
      onRefreshComplete?.();
      return;
    }

    isRefreshing.current = true;

    try {
      const res = await dispatchApi(
        api.search.hit.post({
          query: view.query,
          rows: limit,
          metadata: ['analytic']
        })
      );

      const fetchedHits = res.items ?? [];
      loadHits(fetchedHits);
      setHitIds(fetchedHits.map(h => h.howler.id));

      lastSignature.current = createSignatureFromHits(fetchedHits);
    } finally {
      isRefreshing.current = false;
      onRefreshComplete?.();
    }
  }, [dispatchApi, limit, view?.query, loadHits, onRefreshComplete]);

  const debouncedRefresh = useCallback(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    debounceTimerRef.current = setTimeout(() => {
      refreshView();
    }, DEBOUNCE_TIME);
  }, [refreshView]);

  useEffect(() => {
    if (refreshTick) {
      refreshView();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshTick]);

  useEffect(() => {
    fetchViews([viewId]);
  }, [fetchViews, viewId]);

  useEffect(() => {
    if (!view?.query) {
      return;
    }

    const loadingTimeout = setTimeout(() => setLoading(true), 200);

    refreshView().finally(() => {
      clearTimeout(loadingTimeout);
      setLoading(false);
    });

    return () => {
      clearTimeout(loadingTimeout);
    };
  }, [view?.query, limit, refreshView]);

  // Monitor hits currently in the view for changes that might affect query results
  useEffect(() => {
    if (!hitsSignature || hitIds.length === 0 || !lastSignature.current) {
      lastSignature.current = hitsSignature;
      return;
    }

    // Check if signature actually changed
    if (lastSignature.current === hitsSignature) {
      return;
    }

    debouncedRefresh();
  }, [hitsSignature, hitIds, debouncedRefresh]);

  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  const onClick = useCallback((query: string) => navigate('/hits?query=' + query), [navigate]);

  const getSelectedId = useCallback((event: React.MouseEvent<HTMLDivElement, MouseEvent>) => {
    const target = event.target as HTMLElement;
    const selectedElement = target.closest('[id]') as HTMLElement;

    if (!selectedElement) {
      return;
    }

    return selectedElement.id;
  }, []);

  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <Stack spacing={1} sx={{ p: 1, minHeight: 100 }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="h6">
            {t(view?.title) || <Skeleton variant="text" height="2em" width="100px" />}
          </Typography>
          <IconButton
            size="small"
            component={Link}
            disabled={!view}
            to={view ? buildViewUrl(view) : ''}
            onClick={() => onClick(view.query)}
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
        ) : hits.length > 0 ? (
          <HitContextMenu getSelectedId={getSelectedId}>
            {hits.map(h => (
              <Card
                id={h.howler.id}
                variant="outlined"
                key={h.howler.id}
                sx={{ cursor: 'pointer' }}
                onClick={() => navigate((h.howler.is_bundle ? '/bundles/' : '/hits/') + h.howler.id)}
              >
                <CardContent>
                  <HitBanner layout={HitLayout.DENSE} hit={h} />
                </CardContent>
              </Card>
            ))}
          </HitContextMenu>
        ) : (
          <AppListEmpty />
        )}
      </Stack>
    </Card>
  );
};

export default ViewCard;
