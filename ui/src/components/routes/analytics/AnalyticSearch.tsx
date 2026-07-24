import { Star, StarBorder } from '@mui/icons-material';
import {
  AvatarGroup,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Divider,
  Grid,
  IconButton,
  Stack,
  Tooltip,
  Typography,
  useTheme
} from '@mui/material';
import api from 'api';
import { useAppUser } from 'commons/components/app/hooks';
import SearchResponseProvider, {
  createSearchResponseContext,
  useSearchResponseContext
} from 'components/app/providers/SearchResponseProvider';
import FlexOne from 'components/elements/addons/layout/FlexOne';
import { TuiListProvider, type TuiListItemProps } from 'components/elements/addons/lists';
import { TuiListMethodContext, type TuiListMethodsState } from 'components/elements/addons/lists/TuiListProvider';
import HowlerAvatar from 'components/elements/display/HowlerAvatar';
import ItemManager from 'components/elements/display/ItemManager';
import useMyApi from 'components/hooks/useMyApi';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { Analytic } from 'models/entities/generated/Analytic';
import { useCallback, useContext, useEffect, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { StorageKey } from 'utils/constants';
import { sanitizeLuceneQuery } from 'utils/stringUtils';

const SearchResponseContext = createSearchResponseContext<Analytic>();

const AnalyticSearchBase: FC = () => {
  const theme = useTheme();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const { load } = useContext<TuiListMethodsState<Analytic>>(TuiListMethodContext);
  const [searchParams, setSearchParams] = useSearchParams();
  const pageCount = useMyLocalStorageItem(StorageKey.PAGE_COUNT, 25)[0];
  const appUser = useAppUser<HowlerUser>();

  const { response, request } = useSearchResponseContext(SearchResponseContext);

  const [searching, setSearching] = useState<boolean>(false);
  const [hasError, setHasError] = useState<boolean>(false);
  const [phrase, setPhrase] = useState(searchParams.get('phrase') || '');
  const [offset, setOffset] = useState(parseInt(searchParams.get('offset')!) || 0);

  const addFavourite = useCallback(
    async (analytic: Analytic) => {
      await dispatchApi(api.analytic.favourite.post(analytic.analytic_id!));

      appUser.setUser({
        ...appUser.user,
        favourite_analytics: [...(appUser.user.favourite_analytics ?? []), analytic.analytic_id!]
      });
    },
    [appUser, dispatchApi]
  );

  const removeFavourite = useCallback(
    async (analytic: Analytic) => {
      await dispatchApi(api.analytic.favourite.del(analytic.analytic_id!));

      appUser.setUser({
        ...appUser.user,
        favourite_analytics: (appUser.user.favourite_analytics ?? []).filter(v => v !== analytic.analytic_id)
      });
    },
    [appUser, dispatchApi]
  );

  // Search Handler.
  const onSearch = useCallback(async () => {
    setSearching(true);
    setHasError(false);

    if (phrase) {
      searchParams.set('phrase', phrase);
    } else {
      searchParams.delete('phrase');
    }
    setSearchParams(searchParams, { replace: true });

    try {
      const sanitizedPhrase = sanitizeLuceneQuery(phrase);
      const _response = await request(api.search.analytic.post, {
        query: `name:*${sanitizedPhrase}* OR detections:*${sanitizedPhrase}*`,
        rows: pageCount,
        offset
      });
      load(_response.items.map(u => ({ id: u.analytic_id!, item: u })));
    } catch {
      setHasError(true);
    } finally {
      setSearching(false);
    }
  }, [request, load, offset, pageCount, phrase, searchParams, setSearchParams]);

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

  const onFavourite = useCallback(
    async (event: React.MouseEvent<HTMLButtonElement, MouseEvent>, analytic: Analytic) => {
      event.preventDefault();
      event.stopPropagation();

      if (appUser.user?.favourite_analytics?.includes(analytic.analytic_id!)) {
        await dispatchApi(removeFavourite(analytic));
      } else {
        await dispatchApi(addFavourite(analytic));
      }
    },
    [addFavourite, appUser.user?.favourite_analytics, dispatchApi, removeFavourite]
  );

  // Effect to initialize list of users.
  useEffect(
    () => {
      void onSearch();

      if (!searchParams.has('offset')) {
        searchParams.set('offset', '0');
        setSearchParams(searchParams, { replace: true });
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  useEffect(() => {
    if ((response?.total ?? 0) <= offset) {
      setOffset(0);
      searchParams.set('offset', '0');
      setSearchParams(searchParams, { replace: true });
    }
  }, [offset, response?.total, searchParams, setSearchParams]);

  useEffect(() => {
    if (!searching) {
      void onSearch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offset]);

  // Search result list item renderer.
  const renderer = useCallback(
    ({ item }: TuiListItemProps<Analytic>, classRenderer: () => string) => {
      const filteredContributors = (item.item.contributors ?? []).filter(
        contributor => contributor !== item.item.owner
      );

      return (
        <Card
          key={item.item.name}
          onClick={() => navigate(`/analytics/${item.item.analytic_id}`)}
          variant="outlined"
          className={classRenderer()}
          sx={{
            '&:hover': { borderColor: 'primary.main' },
            transitionProperty: 'border-color',
            cursor: 'pointer',
            mt: 1
          }}
        >
          <CardHeader
            title={
              <Stack direction="row" spacing={1} alignItems="center">
                <span>{item.item.name}</span>
                <FlexOne />
                <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                  {item.item.owner && <HowlerAvatar sx={{ width: 24, height: 24 }} userId={item.item.owner} />}
                  {filteredContributors.length > 0 && <Divider orientation="vertical" flexItem />}
                  <AvatarGroup>
                    {filteredContributors.map(contributor => (
                      <HowlerAvatar key={contributor} sx={{ width: 24, height: 24 }} userId={contributor} />
                    ))}
                  </AvatarGroup>
                </Stack>
                <Tooltip title={t('button.pin')}>
                  <IconButton size="small" onClick={e => onFavourite(e, item.item)}>
                    {appUser.user?.favourite_analytics?.includes(item.item.analytic_id!) ? <Star /> : <StarBorder />}
                  </IconButton>
                </Tooltip>
              </Stack>
            }
          />
          {(item.item.detections?.length ?? 0) > 0 && (
            <CardContent sx={{ paddingTop: 0 }}>
              <Grid container spacing={0.5} sx={{ marginTop: `${theme.spacing(-0.5)} !important` }}>
                {item.item.detections!.slice(0, 5).map(d => (
                  <Grid item key={d}>
                    <Chip variant="outlined" label={d} />
                  </Grid>
                ))}
                {item.item.detections!.length > 5 && (
                  <Grid item>
                    <Tooltip
                      title={
                        <Stack>
                          {item.item.detections!.slice(5).map(d => (
                            <span key={d}>{d}</span>
                          ))}
                        </Stack>
                      }
                    >
                      <Chip variant="outlined" label={`+ ${item.item.detections!.length - 5}`} />
                    </Tooltip>
                  </Grid>
                )}
              </Grid>
            </CardContent>
          )}
        </Card>
      );
    },
    [appUser.user?.favourite_analytics, navigate, onFavourite, t, theme]
  );

  return (
    <ItemManager
      onSearch={onSearch}
      onPageChange={onPageChange}
      phrase={phrase}
      setPhrase={setPhrase}
      hasError={hasError}
      searching={searching}
      aboveSearch={
        <Typography sx={{ fontStyle: 'italic', color: theme.palette.text.disabled, mb: 0.5 }} variant="body2">
          {t('route.analytics.search.prompt')}
        </Typography>
      }
      renderer={renderer}
      response={response!}
      searchPrompt="route.analytics.manager.search"
    />
  );
};

const AnalyticSearch: FC = () => {
  return (
    <TuiListProvider>
      <SearchResponseProvider context={SearchResponseContext} idField="analytic_id">
        <AnalyticSearchBase />
      </SearchResponseProvider>
    </TuiListProvider>
  );
};

export default AnalyticSearch;
