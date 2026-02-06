import {
  ArrowDropDown,
  Delete,
  Edit,
  Language,
  Lock,
  OpenInNew,
  Person,
  Refresh,
  SavedSearch,
  SelectAll
} from '@mui/icons-material';
import { Autocomplete, Chip, CircularProgress, IconButton, Stack, TextField, Tooltip, Typography } from '@mui/material';
import { HitSearchContext } from 'components/app/providers/HitSearchProvider';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import { ViewContext } from 'components/app/providers/ViewProvider';
import ChipPopper from 'components/elements/display/ChipPopper';
import type { View } from 'models/entities/generated/View';
import { memo, useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';

const ViewLink: FC<{ id: number; viewId: string }> = ({ id, viewId }) => {
  const { t } = useTranslation();

  const getCurrentViews = useContextSelector(ViewContext, ctx => ctx.getCurrentViews);
  const views = useContextSelector(ViewContext, ctx => ctx.views);

  const query = useContextSelector(ParameterContext, ctx => ctx.query);
  const sort = useContextSelector(ParameterContext, ctx => ctx.sort);
  const span = useContextSelector(ParameterContext, ctx => ctx.span);
  const currentViews = useContextSelector(ParameterContext, ctx => ctx.views);

  const removeView = useContextSelector(ParameterContext, ctx => ctx.removeView);
  const setParamView = useContextSelector(ParameterContext, ctx => ctx.setView);

  const search = useContextSelector(HitSearchContext, ctx => ctx.search);

  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<View>(null);

  useEffect(() => {
    setLoading(true);
    getCurrentViews({ views: [viewId], ignoreParams: true })
      .then(result => setView(result[0]))
      .finally(() => setLoading(false));
  }, [getCurrentViews, viewId]);

  const viewUrl = useMemo(() => {
    if (view?.view_id) {
      return `/views/${view.view_id}/edit`;
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
  }, [query, sort, span, view]);

  const options = useMemo(
    () => Object.values(views).filter(_view => !!_view && !currentViews?.includes(_view.view_id)),
    [currentViews, views]
  );

  if (loading) {
    return <Chip size="small" icon={<CircularProgress size={12} />} />;
  }

  if (viewId === '') {
    return (
      <ChipPopper
        icon={<SelectAll />}
        label={t('hit.search.view.select')}
        deleteIcon={<ArrowDropDown />}
        toggleOnDelete
        slotProps={{ chip: { size: 'small', color: 'warning' } }}
      >
        <Stack spacing={1} direction="row">
          <Autocomplete
            fullWidth
            size="small"
            options={options}
            getOptionLabel={_view => t(_view.title)}
            renderOption={({ key, ...props }, o) => (
              <li {...props} key={key}>
                <Stack>
                  <Typography variant="body1">{t(o.title)}</Typography>
                  <Typography variant="caption">
                    <code style={{ wordBreak: 'break-all' }}>{o.query}</code>
                  </Typography>
                </Stack>
              </li>
            )}
            renderInput={_params => (
              <TextField {..._params} label={t('hit.search.view.select')} sx={{ minWidth: '210px' }} />
            )}
            onChange={(_event, _view) => setParamView(id, _view.view_id)}
            sx={{ minWidth: '300px' }}
          />
          <Tooltip title={t('hit.search.view.remove')}>
            <IconButton aria-label={t('hit.search.view.remove')} onClick={() => removeView(viewId)}>
              <Delete />
            </IconButton>
          </Tooltip>
        </Stack>
      </ChipPopper>
    );
  }

  if (!view) {
    return (
      <Chip
        size="small"
        role="alert"
        color="error"
        aria-live="assertive"
        aria-atomic="true"
        label={t('view.notfound')}
        onDelete={() => removeView(viewId)}
      />
    );
  }

  return (
    <ChipPopper
      slotProps={{ chip: { size: 'small' } }}
      icon={
        <Tooltip title={t(`route.views.manager.${view.type}`)}>
          {
            {
              readonly: <Lock fontSize="small" aria-label={t(`route.views.manager.${view.type}`)} />,
              global: <Language fontSize="small" aria-label={t(`route.views.manager.${view.type}`)} />,
              personal: <Person fontSize="small" aria-label={t(`route.views.manager.${view.type}`)} />
            }[view.type]
          }
        </Tooltip>
      }
      label={
        <Tooltip title={view.query}>
          <Typography
            role="link"
            sx={{ color: 'text.primary' }}
            variant="body2"
            component={Link}
            to={`/views/${view.view_id}/edit`}
            aria-label={`${t(view.title)} - ${view.query ?? t('unknown')}`}
          >
            {t(view.title)}
          </Typography>
        </Tooltip>
      }
      onDelete={() => removeView(viewId)}
    >
      <Stack direction="row" spacing={0.5} alignItems="center">
        <Tooltip title={view ? t('route.views.edit') : t('route.views.create')}>
          <IconButton
            aria-label={view ? t('route.views.edit') : t('route.views.create')}
            size="small"
            component={Link}
            disabled={(!view && !query) || span?.endsWith('custom')}
            to={viewUrl}
            role="link"
          >
            {view ? <Edit fontSize="small" /> : <SavedSearch />}
          </IconButton>
        </Tooltip>
        <Tooltip title={t('view.refresh')}>
          <IconButton size="small" onClick={() => search(query)} aria-label={t('view.refresh')}>
            <Refresh fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title={t('view.open')}>
          <IconButton
            size="small"
            component={Link}
            to={`/search?query=${view.query}`}
            aria-label={t('view.open')}
            role="link"
          >
            <OpenInNew fontSize="small" />
          </IconButton>
        </Tooltip>
      </Stack>
    </ChipPopper>
  );
};

export default memo(ViewLink);
