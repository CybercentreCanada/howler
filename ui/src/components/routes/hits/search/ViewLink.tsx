import { Close, Edit, OpenInNew, Refresh, SavedSearch } from '@mui/icons-material';
import { Alert, IconButton, Stack, Tooltip, Typography } from '@mui/material';
import { HitSearchContext } from 'components/app/providers/HitSearchProvider';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import { ViewContext } from 'components/app/providers/ViewProvider';
import { has } from 'lodash-es';
import { memo, useMemo, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';

const ViewLink: FC = () => {
  const { t } = useTranslation();

  const query = useContextSelector(ParameterContext, ctx => ctx.query);
  const sort = useContextSelector(ParameterContext, ctx => ctx.sort);
  const span = useContextSelector(ParameterContext, ctx => ctx.span);

  const viewId = useContextSelector(HitSearchContext, ctx => ctx.viewId);
  const search = useContextSelector(HitSearchContext, ctx => ctx.search);

  const viewsReady = useContextSelector(ViewContext, ctx => has(ctx.views, viewId));
  const selectedView = useContextSelector(ViewContext, ctx => ctx.views[viewId]);

  const viewUrl = useMemo(() => {
    if (viewId) {
      return `/views/${viewId}/edit`;
    }

    const keys = [];
    if (query) {
      keys.push(`query=${query}`);
    }

    if (sort) {
      keys.push(`sort=${sort}`);
    }

    if (span) {
      keys.push(`span=${span}`);
    }

    return keys.length > 0 ? `/views/create?${keys.join('&')}` : '/views/create';
  }, [query, sort, span, viewId]);

  const viewButton = useMemo(
    () => (
      <Tooltip title={viewId ? t('route.views.edit') : t('route.views.create')}>
        <IconButton
          size="small"
          component={Link}
          disabled={(!viewId && !query) || span?.endsWith('custom')}
          to={viewUrl}
        >
          {viewId ? <Edit fontSize="small" /> : <SavedSearch />}
        </IconButton>
      </Tooltip>
    ),
    [query, span, t, viewId, viewUrl]
  );

  if (!viewId) {
    return null;
  }

  return selectedView ? (
    <Stack direction="row" spacing={1} alignItems="center">
      <Tooltip title={selectedView.query}>
        <Typography
          sx={{ color: 'text.primary' }}
          variant="body1"
          component={Link}
          to={`/views/${selectedView.view_id}/edit`}
        >
          {t(selectedView.title)}
        </Typography>
      </Tooltip>
      {viewButton}
      {viewId && (
        <IconButton size="small" onClick={() => search(query)}>
          <Tooltip title={t('view.refresh')}>
            <Refresh fontSize="small" />
          </Tooltip>
        </IconButton>
      )}
      {viewId && (
        <IconButton size="small" component={Link} to={`/search?query=${selectedView.query}`}>
          <Tooltip title={t('view.open')}>
            <OpenInNew fontSize="small" />
          </Tooltip>
        </IconButton>
      )}
    </Stack>
  ) : (
    viewsReady && (
      <Alert
        variant="outlined"
        severity="error"
        action={
          <IconButton size="small" component={Link} to="/search">
            <Close fontSize="small" />
          </IconButton>
        }
      >
        {t('view.notfound')}
      </Alert>
    )
  );
};

export default memo(ViewLink);
