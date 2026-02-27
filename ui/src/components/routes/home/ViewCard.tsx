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
import { useNavigate } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import Throttler from 'utils/Throttler';

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

const MIN_REFRESH_INTERVAL = 1000; // Minimum 1 second between refreshes
const COOLDOWN_PERIOD = 1500; // Cooldown after refresh to prevent false triggers
const DEBOUNCE_TIME = 500; // Base debounce time for signature changes

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
  const cooldownTimerRef = useRef<ReturnType<typeof setTimeout>>(null);
  const isRefreshing = useRef(false);
  const lastRefreshTime = useRef<number>(0);
  const lastSignature = useRef<string>('');
  const isInCooldown = useRef(false);
  const throttlerRef = useRef(new Throttler(DEBOUNCE_TIME));
  const isInitialized = useRef(false);

  const view = useContextSelector(ViewContext, ctx => ctx.views[viewId]);
  const fetchViews = useContextSelector(ViewContext, ctx => ctx.fetchViews);
  const loadHits = useHitContextSelector(ctx => ctx.loadHits);

  // Subscribe to hits from HitProvider cache, automatically getting updates via WebSocket
  // Use a selector that only returns hits for this view to avoid unnecessary re-renders
  const hits = useHitContextSelector(useCallback(ctx => hitIds.map(id => ctx.hits[id]).filter(Boolean), [hitIds]));

  // Create a stable signature that only changes when relevant fields change
  const hitsSignature = useMemo(() => createSignatureFromHits(hits), [hits]);

  // Refresh the view to re-evaluate query criteria
  const refreshView = useCallback(async () => {
    if (!view?.query) {
      return;
    }

    // Enforce minimum refresh interval to prevent spam
    const now = Date.now();
    if (now - lastRefreshTime.current < MIN_REFRESH_INTERVAL) {
      return;
    }

    if (isRefreshing.current) {
      return;
    }

    isRefreshing.current = true;
    lastRefreshTime.current = now;

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

      // Update signature to match the fresh data to prevent false triggers
      lastSignature.current = createSignatureFromHits(fetchedHits);

      // Enter cooldown period to prevent detecting our own refresh as a change
      isInCooldown.current = true;
      if (cooldownTimerRef.current) {
        clearTimeout(cooldownTimerRef.current);
      }
      cooldownTimerRef.current = setTimeout(() => {
        isInCooldown.current = false;
      }, COOLDOWN_PERIOD);
    } finally {
      isRefreshing.current = false;
      onRefreshComplete?.();
    }
  }, [dispatchApi, limit, view?.query, loadHits, onRefreshComplete]);

  /**
   * Debounced refresh to handle rapid WebSocket updates
   */
  const debouncedRefresh = useCallback(() => {
    throttlerRef.current.debounce(() => {
      if (!isRefreshing.current) {
        refreshView();
      }
    });
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
    if (!hitsSignature || hitIds.length === 0) {
      return;
    }

    // Don't trigger during cooldown period (after a refresh completes)
    if (isInCooldown.current) {
      return;
    }

    // Check if signature actually changed
    if (lastSignature.current === hitsSignature) {
      return;
    }

    // First time initialization - don't trigger refresh
    if (!isInitialized.current) {
      isInitialized.current = true;
      lastSignature.current = hitsSignature;
      return;
    }

    lastSignature.current = hitsSignature;
    debouncedRefresh();
  }, [hitsSignature, hitIds, debouncedRefresh]);

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      if (cooldownTimerRef.current) {
        clearTimeout(cooldownTimerRef.current);
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
          <IconButton size="small" onClick={() => onClick(view.query)}>
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
