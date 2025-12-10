import { ChevronLeft, Close, ManageSearch } from '@mui/icons-material';
import {
  Box,
  Card,
  Checkbox,
  Collapse,
  Drawer,
  Fab,
  IconButton,
  Stack,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme
} from '@mui/material';
import { HitContext } from 'components/app/providers/HitProvider';
import HitSearchProvider, { HitSearchContext } from 'components/app/providers/HitSearchProvider';
import ParameterProvider, { ParameterContext } from 'components/app/providers/ParameterProvider';
import { ViewContext } from 'components/app/providers/ViewProvider';
import FlexOne from 'components/elements/addons/layout/FlexOne';
import FlexPort from 'components/elements/addons/layout/FlexPort';
import HitSummary from 'components/elements/hit/HitSummary';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import ErrorBoundary from 'components/routes/ErrorBoundary';
import dayjs from 'dayjs';
import { has, isNull } from 'lodash-es';
import type { FC, ReactNode } from 'react';
import { memo, useCallback, useEffect, useMemo, useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { useLocation, useParams, useSearchParams } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import { StorageKey } from 'utils/constants';
import InformationPane from './InformationPane';
import SearchPane from './SearchPane';
import HitGrid from './grid/HitGrid';

// https://github.com/jsx-eslint/eslint-plugin-react/blob/master/docs/rules/display-name.md
const Wrapper = memo<{ show: boolean; showDrawer: boolean; children: ReactNode; onClose: () => void }>(
  ({ show, showDrawer, children, onClose }) => {
    return (
      <ErrorBoundary>
        {showDrawer ? (
          <Drawer
            onClose={onClose}
            open={show}
            anchor="right"
            PaperProps={{ sx: { backgroundImage: 'none', overflow: 'hidden', width: '75vw' } }}
          >
            {children}
          </Drawer>
        ) : (
          <FlexPort disableOverflow>{children}</FlexPort>
        )}
      </ErrorBoundary>
    );
  }
);

const HitBrowser: FC = () => {
  const { t } = useTranslation();
  const theme = useTheme();

  const views = useContextSelector(ViewContext, ctx => ctx.views);
  const fetchViews = useContextSelector(ViewContext, ctx => ctx.fetchViews);

  const selected = useContextSelector(ParameterContext, ctx => ctx.selected);
  const setSelected = useContextSelector(ParameterContext, ctx => ctx.setSelected);
  const query = useContextSelector(ParameterContext, ctx => ctx.query);
  const setQuery = useContextSelector(ParameterContext, ctx => ctx.setQuery);
  const setOffset = useContextSelector(ParameterContext, ctx => ctx.setOffset);

  const selectedHits = useContextSelector(HitContext, ctx => ctx.selectedHits);
  const addHitToSelection = useContextSelector(HitContext, ctx => ctx.addHitToSelection);
  const removeHitFromSelection = useContextSelector(HitContext, ctx => ctx.removeHitFromSelection);
  const clearSelectedHits = useContextSelector(HitContext, ctx => ctx.clearSelectedHits);

  const searchPaneWidth = useMyLocalStorageItem(StorageKey.SEARCH_PANE_WIDTH, null)[0];
  const forceDrawer = useMyLocalStorageItem(StorageKey.FORCE_DRAWER, false)[0];

  const displayType = useContextSelector(HitSearchContext, ctx => ctx.displayType);
  const viewId = useContextSelector(HitSearchContext, ctx => ctx.viewId);
  const response = useContextSelector(HitSearchContext, ctx => ctx.response);

  const queryHistory = useContextSelector(HitSearchContext, ctx => ctx?.queryHistory ?? {});
  const setQueryHistory = useContextSelector(HitSearchContext, ctx => ctx?.setQueryHistory);

  const setQueryList = useMyLocalStorageItem(StorageKey.QUERY_HISTORY, '')[1];

  const location = useLocation();
  const routeParams = useParams();
  const [searchParams] = useSearchParams();

  const [show, setShow] = useState(!!selected);
  useEffect(() => setShow(!!selected), [selected]);

  const showDrawer = useMediaQuery(theme.breakpoints.down(1600)) || forceDrawer || displayType === 'grid';

  // State that makes up the request
  const summaryQuery = useMemo(() => {
    const bundle = location.pathname.startsWith('/bundles') && routeParams.id;

    let _fullQuery = query;
    if (bundle) {
      _fullQuery = `(howler.bundles:${bundle}) AND (${_fullQuery})`;
    } else if (viewId) {
      _fullQuery = `(${views[viewId]?.query || 'howler.id:*'}) AND (${_fullQuery})`;
    }

    return _fullQuery;
  }, [location.pathname, query, routeParams.id, views, viewId]);

  const showSelectBar = useMemo(() => {
    if (selectedHits.length > 1) {
      return true;
    }

    if (selectedHits.length === 1 && selected && selectedHits[0]?.howler.id !== selected) {
      return true;
    }

    return false;
  }, [selected, selectedHits]);

  useEffect(() => {
    const newQuery = searchParams.get('query');
    if (newQuery) {
      setQueryHistory(_queryHistory => ({
        ..._queryHistory,
        [newQuery]: new Date().toISOString()
      }));
    }
  }, [searchParams, setQueryHistory]);

  useEffect(() => {
    setQueryList(JSON.stringify(queryHistory));
  }, [queryHistory, setQueryList]);

  useEffect(() => {
    // On load check to filter out any queries older than one month
    setQueryHistory(_queryHistory => {
      const filterQueryTime = dayjs().subtract(1, 'month').toISOString();

      return Object.fromEntries(Object.entries(_queryHistory).filter(([_, value]) => value > filterQueryTime));
    });
  }, [setQueryHistory]);

  useEffect(() => {
    if (!location.pathname.startsWith('/views') || !viewId || has(views, viewId)) {
      return;
    }

    fetchViews([viewId]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname, viewId]);

  const onClose = useCallback(() => {
    setSelected(null);
  }, [setSelected]);

  useEffect(() => {
    if (
      selected &&
      response &&
      !response.items.some(_hit => _hit.howler.id === selected) &&
      (!location.pathname.startsWith('/bundles') || routeParams.id !== selected)
    ) {
      setSelected(null);
      if (selectedHits.length < 2) {
        removeHitFromSelection(selected);
      }
      return;
    }

    if (selected && !selectedHits.some(_hit => _hit?.howler.id === selected)) {
      addHitToSelection(selected);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [addHitToSelection, location.pathname, removeHitFromSelection, response, routeParams.id, selected, setSelected]);

  return (
    <Stack direction="row" flex={1} sx={{ overflow: 'hidden' }}>
      <Box
        position="relative"
        flex={1.15}
        height="100%"
        display="flex"
        sx={[{ overflow: 'auto' }, displayType === 'list' && !isNull(searchPaneWidth) && { maxWidth: searchPaneWidth }]}
      >
        <ErrorBoundary>{displayType === 'list' ? <SearchPane /> : <HitGrid />}</ErrorBoundary>
        <Collapse
          in={showSelectBar}
          unmountOnExit
          sx={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            backgroundColor: theme.palette.background.paper,
            py: 1,
            px: 2
          }}
        >
          <Stack direction="row" alignItems="center" spacing={1}>
            <Tooltip title={t('hit.search.select.all')}>
              <Checkbox
                size="small"
                checked={
                  !!response?.items.every(_hit1 => selectedHits.some(_hit2 => _hit1.howler.id === _hit2.howler.id))
                }
                onChange={(__, checked) =>
                  checked ? response.items.forEach(_hit => addHitToSelection(_hit.howler.id)) : clearSelectedHits()
                }
              />
            </Tooltip>
            <Typography>
              <Trans i18nKey="hit.search.selected" values={{ size: selectedHits.length }} />
            </Typography>

            <FlexOne />

            <Tooltip title={t('hit.search.select.clear')}>
              <IconButton
                size="small"
                onClick={() => {
                  setSelected(null);
                  clearSelectedHits();
                }}
              >
                <Close />
              </IconButton>
            </Tooltip>
            <Tooltip title={t('hit.search.select.view')}>
              <IconButton
                size="small"
                onClick={() => {
                  setOffset(0);
                  setQuery(`howler.id:(${selectedHits.map(hit => hit.howler.id).join(' OR ')})`);
                }}
              >
                <ManageSearch />
              </IconButton>
            </Tooltip>
          </Stack>
        </Collapse>
      </Box>
      <Wrapper show={show} showDrawer={showDrawer} onClose={() => setShow(false)}>
        <HitSummary query={summaryQuery} response={response} />
        <Card
          variant="outlined"
          sx={[
            {
              zIndex: 100,
              overflow: 'visible',
              position: 'absolute',
              top: 0,
              bottom: 0,
              left: '100%',
              right: 0,
              borderTop: 0,
              borderBottom: 0,
              transition: theme.transitions.create('left')
            },
            selected && {
              left: theme.spacing(5)
            },
            location.pathname.startsWith('/bundles') &&
              routeParams.id && {
                left: 0
              }
          ]}
        >
          <InformationPane onClose={onClose} />
          {selected && !(location.pathname.startsWith('/bundles') && routeParams.id) && (
            <Box
              onClick={onClose}
              sx={{
                cursor: 'pointer',
                position: 'absolute',
                right: '100%',
                width: theme.spacing(5),
                top: 0,
                bottom: 0,
                background: `linear-gradient(to right, transparent, ${theme.palette.background.paper})`
              }}
            />
          )}
        </Card>
      </Wrapper>
      {showDrawer && (
        <Fab
          onClick={() => setShow(_show => !_show)}
          color="primary"
          sx={{
            position: 'fixed',
            right: show ? `calc(100% - ${theme.spacing(8)})` : theme.spacing(2),
            bottom: showSelectBar ? theme.spacing(6) : theme.spacing(1),
            zIndex: 1201,
            transition: theme.transitions.create(['right', 'bottom'])
          }}
        >
          <ChevronLeft sx={{ transition: 'rotate 250ms', rotate: show ? '180deg' : '0deg' }} />
        </Fab>
      )}
    </Stack>
  );
};

const HitBrowserProvider: FC = () => {
  return (
    <ParameterProvider>
      <HitSearchProvider>
        <HitBrowser />
      </HitSearchProvider>
    </ParameterProvider>
  );
};

export default HitBrowserProvider;
