import { OpenInNew } from '@mui/icons-material';
import { Card, CardContent, IconButton, Skeleton, Stack, Typography } from '@mui/material';
import api from 'api';
import AppListEmpty from 'commons/components/display/AppListEmpty';
import { ViewContext } from 'components/app/providers/ViewProvider';
import HitBanner from 'components/elements/hit/HitBanner';
import { HitLayout } from 'components/elements/hit/HitLayout';
import useMyApi from 'components/hooks/useMyApi';
import type { Hit } from 'models/entities/generated/Hit';
import type { FC } from 'react';
import { useCallback, useEffect, useState } from 'react';
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

  const [hits, setHits] = useState<Hit[]>([]);
  const [loading, setLoading] = useState(false);

  const view = useContextSelector(ViewContext, ctx => ctx.views[viewId]);
  const fetchViews = useContextSelector(ViewContext, ctx => ctx.fetchViews);

  useEffect(() => {
    fetchViews([viewId]);
  }, [fetchViews, viewId]);

  useEffect(() => {
    if (!view?.query) {
      return;
    }

    const timeout = setTimeout(() => setLoading(true), 200);

    dispatchApi(
      api.search.hit.post({
        query: view.query,
        rows: limit
      })
    )
      .then(res => setHits(res.items ?? []))
      .finally(() => {
        clearTimeout(timeout);
        setLoading(false);
      });
  }, [dispatchApi, limit, view?.query]);

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
