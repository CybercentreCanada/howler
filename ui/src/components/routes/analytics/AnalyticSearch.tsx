import { SsidChart, Star, StarBorder } from '@mui/icons-material';
import {
  AvatarGroup,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Divider,
  Grid,
  IconButton,
  InputAdornment,
  Stack,
  Tooltip,
  Typography,
  useTheme
} from '@mui/material';
import api from 'api';
import type { HowlerSearchResponse } from 'api/search';
import { useAppUser } from 'commons/components/app/hooks';
import useLocalStorageItem from 'commons/components/utils/hooks/useLocalStorageItem';
import { AnalyticContext } from 'components/app/providers/AnalyticProvider';
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

type RuleTypes = -1 | 0 | 1;

const AnalyticSearchBase: FC = () => {
  const theme = useTheme();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const { load } = useContext<TuiListMethodsState<Analytic>>(TuiListMethodContext);
  const [searchParams, setSearchParams] = useSearchParams();
  const pageCount = useMyLocalStorageItem(StorageKey.PAGE_COUNT, 25)[0];
  const appUser = useAppUser<HowlerUser>();
  const { addFavourite, removeFavourite } = useContext(AnalyticContext);

  const [onlyRules, setOnlyRules] = useLocalStorageItem<RuleTypes>(StorageKey.ONLY_RULES, 0);
  const [searching, setSearching] = useState<boolean>(false);
  const [hasError, setHasError] = useState<boolean>(false);
  const [phrase, setPhrase] = useState(searchParams.get('phrase') || '');
  const [offset, setOffset] = useState(parseInt(searchParams.get('offset')) || 0);
  const [response, setResponse] = useState<HowlerSearchResponse<Analytic>>(null);

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
      const _response = await dispatchApi(
        api.search.analytic.post({
          query:
            `name:*${sanitizedPhrase}* OR detections:*${sanitizedPhrase}*` +
            (onlyRules > 0 ? ' AND _exists_:rule_type' : onlyRules < 0 ? ' AND -_exists_:rule_type' : ''),
          rows: pageCount,
          offset
        })
      );
      setResponse(_response);
      load(_response.items.map(u => ({ id: u.analytic_id, item: u })));
    } catch (e) {
      setHasError(true);
    } finally {
      setSearching(false);
    }
  }, [dispatchApi, load, offset, onlyRules, pageCount, phrase, searchParams, setSearchParams]);

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

      if (appUser.user?.favourite_analytics.includes(analytic.analytic_id)) {
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
      onSearch();

      if (!searchParams.has('offset')) {
        searchParams.set('offset', '0');
        setSearchParams(searchParams, { replace: true });
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [onlyRules]
  );

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
                {item.item.rule_type && (
                  <>
                    <Tooltip title={t('route.analytics.rule')}>
                      <SsidChart color="info" />
                    </Tooltip>
                    <code
                      style={{
                        fontSize: '.55em',
                        backgroundColor: theme.palette.background.paper,
                        padding: theme.spacing(0.5),
                        borderRadius: theme.shape.borderRadius,
                        border: `thin solid ${theme.palette.divider}`
                      }}
                    >
                      {item.item.rule_type}
                    </code>
                  </>
                )}
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
                    {appUser.user?.favourite_analytics?.includes(item.item.analytic_id) ? <Star /> : <StarBorder />}
                  </IconButton>
                </Tooltip>
              </Stack>
            }
          />
          {item.item.detections?.length > 0 && (
            <CardContent sx={{ paddingTop: 0 }}>
              <Grid container spacing={0.5} sx={{ marginTop: `${theme.spacing(-0.5)} !important` }}>
                {item.item.detections.slice(0, 5).map(d => (
                  <Grid item key={d}>
                    <Chip size="small" variant="outlined" label={d} />
                  </Grid>
                ))}
                {item.item.detections.length > 5 && (
                  <Grid item>
                    <Tooltip
                      title={
                        <Stack>
                          {item.item.detections.slice(5).map(d => (
                            <span key={d}>{d}</span>
                          ))}
                        </Stack>
                      }
                    >
                      <Chip size="small" variant="outlined" label={`+ ${item.item.detections.length - 5}`} />
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
      searchAdornment={
        <InputAdornment position="end">
          <Tooltip
            title={t(
              `route.analytics.search.filter.rules.${onlyRules < 0 ? 'hide' : onlyRules > 0 ? 'show' : 'toggle'}`
            )}
          >
            <IconButton onClick={() => setOnlyRules((((onlyRules + 2) % 3) - 1) as -1 | 0 | 1)}>
              <SsidChart
                color={onlyRules < 0 ? 'error' : onlyRules > 0 ? 'info' : 'inherit'}
                sx={{ transition: theme.transitions.create(['color']) }}
              />
            </IconButton>
          </Tooltip>
        </InputAdornment>
      }
      aboveSearch={
        <Typography sx={{ fontStyle: 'italic', color: theme.palette.text.disabled, mb: 0.5 }} variant="body2">
          {t('route.analytics.search.prompt')}
        </Typography>
      }
      renderer={renderer}
      response={response}
      searchPrompt="route.analytics.manager.search"
    />
  );
};

const AnalyticSearch: FC = () => {
  return (
    <TuiListProvider>
      <AnalyticSearchBase />
    </TuiListProvider>
  );
};

export default AnalyticSearch;
