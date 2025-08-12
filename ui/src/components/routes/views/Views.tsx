import { Clear, Edit, SavedSearch, Star, StarBorder } from '@mui/icons-material';
import {
  Autocomplete,
  Card,
  Checkbox,
  IconButton,
  Skeleton,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography
} from '@mui/material';
import api from 'api';
import type { HowlerSearchResponse } from 'api/search';
import { useAppUser } from 'commons/components/app/hooks';
import { ViewContext } from 'components/app/providers/ViewProvider';
import FlexOne from 'components/elements/addons/layout/FlexOne';
import { TuiListProvider, type TuiListItemProps } from 'components/elements/addons/lists';
import { TuiListMethodContext, type TuiListMethodsState } from 'components/elements/addons/lists/TuiListProvider';
import HowlerAvatar from 'components/elements/display/HowlerAvatar';
import ItemManager from 'components/elements/display/ItemManager';
import { ViewTitle } from 'components/elements/view/ViewTitle';
import useMyApi from 'components/hooks/useMyApi';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import { isNull, omitBy, size } from 'lodash-es';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { View } from 'models/entities/generated/View';
import React, { useCallback, useContext, useEffect, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import { StorageKey } from 'utils/constants';
import { sanitizeLuceneQuery } from 'utils/stringUtils';

const FIELDS_TO_SEARCH = ['title', 'query', 'sort', 'type', 'owner'];

const ViewsBase: FC = () => {
  const { t } = useTranslation();
  const { user } = useAppUser<HowlerUser>();
  const navigate = useNavigate();
  const { dispatchApi } = useMyApi();

  const fetchViews = useContextSelector(ViewContext, ctx => ctx.fetchViews);
  const addFavourite = useContextSelector(ViewContext, ctx => ctx.addFavourite);
  const removeFavourite = useContextSelector(ViewContext, ctx => ctx.removeFavourite);
  const removeView = useContextSelector(ViewContext, ctx => ctx.removeView);
  const views = useContextSelector(ViewContext, ctx => ctx.views);
  const defaultView = useContextSelector(ViewContext, ctx => ctx.defaultView);
  const setDefaultView = useContextSelector(ViewContext, ctx => ctx.setDefaultView);

  const [searchParams, setSearchParams] = useSearchParams();
  const { load } = useContext<TuiListMethodsState<View>>(TuiListMethodContext);
  const pageCount = useMyLocalStorageItem(StorageKey.PAGE_COUNT, 25)[0];

  const [phrase, setPhrase] = useState<string>('');
  const [offset, setOffset] = useState(parseInt(searchParams.get('offset')) || 0);
  const [response, setResponse] = useState<HowlerSearchResponse<View>>(null);
  const [type, setType] = useState<'personal' | 'global'>((searchParams.get('type') as 'personal' | 'global') || null);
  const [hasError, setHasError] = useState(false);
  const [searching, setSearching] = useState(false);
  const [favouritesOnly, setFavouritesOnly] = useState(false);
  const [defaultViewOpen, setDefaultViewOpen] = useState(false);
  const [defaultViewLoading, setDefaultViewLoading] = useState(false);

  const onSearch = useCallback(async () => {
    try {
      setSearching(true);
      setHasError(false);

      if (phrase) {
        searchParams.set('phrase', phrase);
      } else {
        searchParams.delete('phrase');
      }
      setSearchParams(searchParams, { replace: true });

      const searchTerm = phrase ? `*${sanitizeLuceneQuery(phrase)}*` : '*';
      const phraseQuery = FIELDS_TO_SEARCH.map(_field => `${_field}:${searchTerm}`).join(' OR ');
      const typeQuery = `(type:global OR owner:(${user.username} OR none)) AND type:(${type ?? '*'}${
        type.includes('personal') ? ' OR readonly' : ''
      })`;
      const favouritesQuery =
        favouritesOnly && user.favourite_views.length > 0 ? ` AND view_id:(${user.favourite_views.join(' OR ')})` : '';

      setResponse(
        await dispatchApi(
          api.search.view.post({
            query: `(${phraseQuery}) AND ${typeQuery}${favouritesQuery}`,
            rows: pageCount,
            offset
          })
        )
      );
    } catch (e) {
      setHasError(true);
    } finally {
      setSearching(false);
    }
  }, [
    phrase,
    setSearchParams,
    searchParams,
    user.username,
    user.favourite_views,
    type,
    favouritesOnly,
    dispatchApi,
    pageCount,
    offset
  ]);

  // Load the items into list when response changes.
  // This hook should only trigger when the 'response' changes.
  useEffect(() => {
    if (response) {
      load(
        response.items.map(item => ({
          id: item.view_id,
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

  const onDelete = useCallback(
    async (event: React.MouseEvent<HTMLButtonElement, MouseEvent>, id: string) => {
      event.preventDefault();
      event.stopPropagation();

      await removeView(id);

      onSearch();
    },
    [onSearch, removeView]
  );

  const onFavourite = useCallback(
    async (event: React.MouseEvent<HTMLButtonElement, MouseEvent>, id: string) => {
      event.preventDefault();

      if (user.favourite_views?.includes(id)) {
        await removeFavourite(id);
        if (user.favourite_views?.length < 2) {
          setFavouritesOnly(false);
        }
      } else {
        await addFavourite(id);
      }
    },
    [addFavourite, removeFavourite, user.favourite_views]
  );

  const onDefaultViewOpen = useCallback(async () => {
    setDefaultViewOpen(true);
    setDefaultViewLoading(true);

    try {
      await fetchViews();
    } finally {
      setDefaultViewLoading(false);
    }
  }, [fetchViews]);

  const onTypeChange = useCallback(
    async (_type: 'personal' | 'global' | null) => {
      setType(_type);

      if (_type) {
        searchParams.delete('type');
        searchParams.set('type', _type);
        setSearchParams(searchParams, { replace: true });
      } else if (searchParams.has('type')) {
        searchParams.delete('type');
        setSearchParams(searchParams, { replace: true });
      }
    },
    [searchParams, setSearchParams]
  );

  useEffect(() => {
    let changed = false;
    if (!searchParams.has('offset')) {
      searchParams.set('offset', '0');
      changed = true;
    }

    if (searchParams.has('type') && !['personal', 'global'].includes(searchParams.get('type'))) {
      searchParams.delete('type');
      changed = true;
    }

    if (changed) {
      setSearchParams(searchParams, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    if (response?.total <= offset) {
      setOffset(0);
      searchParams.set('offset', '0');
      setSearchParams(searchParams, { replace: true });
    }
  }, [offset, response?.total, searchParams, setSearchParams]);

  useEffect(() => {
    if (!searching) {
      onSearch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offset, favouritesOnly, type]);

  return (
    <ItemManager
      onSearch={onSearch}
      onPageChange={onPageChange}
      phrase={phrase}
      setPhrase={setPhrase}
      hasError={hasError}
      searching={searching}
      searchFilters={
        <Stack direction="row" spacing={1} alignItems="center">
          <ToggleButtonGroup
            sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}
            size="small"
            value={type}
            exclusive
            onChange={(__, _type) => onTypeChange(_type)}
          >
            <ToggleButton value="personal" aria-label="personal">
              {t('route.views.manager.personal')}
            </ToggleButton>
            <ToggleButton value="global" aria-label="global">
              {t('route.views.manager.global')}
            </ToggleButton>
          </ToggleButtonGroup>
        </Stack>
      }
      aboveSearch={
        <Typography
          sx={theme => ({ fontStyle: 'italic', color: theme.palette.text.disabled, mb: 0.5 })}
          variant="body2"
        >
          {t('route.views.search.prompt')}
        </Typography>
      }
      afterSearch={
        size(views) > 0 ? (
          <Autocomplete
            open={defaultViewOpen}
            loading={defaultViewLoading}
            onOpen={onDefaultViewOpen}
            onClose={() => setDefaultViewOpen(false)}
            options={Object.values(omitBy(views, isNull))}
            renderOption={({ key, ...props }, o) => (
              <li {...props} key={key}>
                <Stack>
                  <Typography variant="body1">{t(o.title)}</Typography>
                  <Typography variant="caption">
                    <code>{o.query}</code>
                  </Typography>
                </Stack>
              </li>
            )}
            renderInput={params => (
              <TextField {...params} label={t('route.views.manager.default')} sx={{ minWidth: '300px' }} />
            )}
            filterOptions={(_views, { inputValue }) =>
              _views.filter(
                v =>
                  t(v.title).toLowerCase().includes(inputValue.toLowerCase()) ||
                  v.query.toLowerCase().includes(inputValue.toLowerCase())
              )
            }
            getOptionLabel={(v: View) => t(v.title)}
            isOptionEqualToValue={(view, value) => view.view_id === value.view_id}
            value={views[defaultView] ?? null}
            onChange={(_, option: View) => setDefaultView(option?.view_id)}
          />
        ) : (
          <Skeleton variant="rounded" width="300px" height="initial" />
        )
      }
      belowSearch={
        <Stack direction="row" spacing={1} alignItems="center">
          <Checkbox
            size="small"
            disabled={user.favourite_views?.length < 1}
            checked={favouritesOnly}
            onChange={(_, checked) => setFavouritesOnly(checked)}
          />
          <Typography variant="body1" sx={theme => ({ color: theme.palette.text.disabled })}>
            {t('route.views.manager.favourites')}
          </Typography>
        </Stack>
      }
      renderer={({ item }: TuiListItemProps<View>, classRenderer) => (
        <Card
          key={item.item.view_id}
          variant="outlined"
          sx={{ p: 1, mb: 1, transitionProperty: 'border-color', '&:hover': { borderColor: 'primary.main' } }}
          className={classRenderer()}
        >
          <Stack
            direction="row"
            alignItems="center"
            spacing={1}
            sx={{ color: 'inherit', textDecoration: 'none' }}
            component={Link}
            to={`/views/${item.item.view_id}`}
          >
            <ViewTitle {...item.item} />
            <FlexOne />
            {((item.item.owner === user.username && item.item.type !== 'readonly') ||
              (item.item.type === 'global' && user.is_admin)) && (
              <Tooltip title={t('button.edit')}>
                <IconButton component={Link} to={`/views/${item.item.view_id}/edit?query=${item.item.query}`}>
                  <Edit />
                </IconButton>
              </Tooltip>
            )}
            {item.item.owner === user.username && item.item.type !== 'readonly' && (
              <Tooltip title={t('button.delete')}>
                <IconButton onClick={event => onDelete(event, item.item.view_id)}>
                  <Clear />
                </IconButton>
              </Tooltip>
            )}
            {item.item.type === 'global' && item.item.owner !== user.username && (
              <Tooltip title={item.item.owner}>
                <div>
                  <HowlerAvatar
                    sx={{ width: 24, height: 24, marginRight: '8px !important', marginLeft: '8px !important' }}
                    userId={item.item.owner}
                  />
                </div>
              </Tooltip>
            )}
            <Tooltip title={t('button.pin')}>
              <IconButton onClick={e => onFavourite(e, item.item.view_id)}>
                {user.favourite_views?.includes(item.item.view_id) ? <Star /> : <StarBorder />}
              </IconButton>
            </Tooltip>
          </Stack>
        </Card>
      )}
      response={response}
      searchPrompt="route.views.manager.search"
      onCreate={() => navigate('/views/create')}
      createPrompt="route.views.create"
      createIcon={<SavedSearch sx={{ mr: 1 }} />}
    />
  );
};

const Views = () => {
  return (
    <TuiListProvider>
      <ViewsBase />
    </TuiListProvider>
  );
};

export default Views;
