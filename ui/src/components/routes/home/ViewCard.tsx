import { OpenInNew } from '@mui/icons-material';
import { Card, CardContent, IconButton, Skeleton, Stack, Typography } from '@mui/material';
import api from 'api';
import AppListEmpty from 'commons/components/display/AppListEmpty';
import { useHitContextSelector } from 'components/app/providers/HitProvider';
import { ViewContext } from 'components/app/providers/ViewProvider';
import HitBanner from 'components/elements/hit/HitBanner';
import { HitLayout } from 'components/elements/hit/HitLayout';
import useMyApi from 'components/hooks/useMyApi';
import type { FC } from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';

export interface ViewSettings {
  viewId: string;
  limit: number;
}

const ViewCard: FC<ViewSettings> = ({ viewId, limit }) => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();

  const [hitIds, setHitIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const lastHitVersions = useRef<{ [id: string]: any }>({});

  const view = useContextSelector(ViewContext, ctx => ctx.views[viewId]);
  const fetchViews = useContextSelector(ViewContext, ctx => ctx.fetchViews);
  const loadHits = useHitContextSelector(ctx => ctx.loadHits);

  // Subscribe to hits from HitProvider cache, automatically getting updates via WebSocket
  const cachedHits = useHitContextSelector(ctx => ctx.hits);

  // Derive the current hits from the cached hits using our stored IDs
  const hits = useMemo(() => hitIds.map(id => cachedHits[id]).filter(Boolean), [hitIds, cachedHits]);

  // Refresh the view to re-evaluate query criteria
  const refreshView = useCallback(() => {
    if (!view?.query) {
      return;
    }

    dispatchApi(
      api.search.hit.post({
        query: view.query,
        rows: limit,
        metadata: ['analytic']
      })
    ).then(res => {
      const fetchedHits = res.items ?? [];
      loadHits(fetchedHits);
      setHitIds(fetchedHits.map(h => h.howler.id));
    });
  }, [dispatchApi, limit, view?.query, loadHits]);

  useEffect(() => {
    fetchViews([viewId]);
  }, [fetchViews, viewId]);

  useEffect(() => {
    if (!view?.query) {
      return;
    }

    const timeout = setTimeout(() => setLoading(true), 200);

    refreshView();

    clearTimeout(timeout);
    setLoading(false);
  }, [view?.query, refreshView]);

  // Re-evaluate the view when any of its hits are updated
  useEffect(() => {
    // Only refresh if one of OUR hits was actually updated
    let shouldRefresh = false;

    for (const id of hitIds) {
      const currentHit = cachedHits[id];
      if (currentHit) {
        const lastVersion = lastHitVersions.current[id];

        // Check if this hit has been updated (deep comparison on the hit object)
        if (lastVersion && JSON.stringify(lastVersion) !== JSON.stringify(currentHit)) {
          shouldRefresh = true;
          break;
        }

        // Store the current version for future comparisons
        lastHitVersions.current[id] = currentHit;
      }
    }

    if (shouldRefresh) {
      console.log('ViewCard: Hit update detected, refreshing view', viewId);
      refreshView();
    }
  }, [cachedHits, hitIds, refreshView]);

  const onClick = useCallback((query: string) => navigate('/hits?query=' + query), [navigate]);

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
          hits.map(h => (
            <Card
              variant="outlined"
              key={h.howler.id}
              sx={{ cursor: 'pointer' }}
              onClick={() => navigate((h.howler.is_bundle ? '/bundles/' : '/hits/') + h.howler.id)}
            >
              <CardContent>
                <HitBanner layout={HitLayout.DENSE} hit={h} />
              </CardContent>
            </Card>
          ))
        ) : (
          <AppListEmpty />
        )}
      </Stack>
    </Card>
  );
};

export default ViewCard;
