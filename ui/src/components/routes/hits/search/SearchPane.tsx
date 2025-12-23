import { Close, ErrorOutline, List, SavedSearch, TableChart, Terminal } from '@mui/icons-material';
import {
  Box,
  IconButton,
  LinearProgress,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme
} from '@mui/material';
import { grey } from '@mui/material/colors';
import AppListEmpty from 'commons/components/display/AppListEmpty';
import PageCenter from 'commons/components/pages/PageCenter';
import { HitContext } from 'components/app/providers/HitProvider';
import { HitSearchContext } from 'components/app/providers/HitSearchProvider';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import { ViewContext } from 'components/app/providers/ViewProvider';
import FlexOne from 'components/elements/addons/layout/FlexOne';
import FlexPort from 'components/elements/addons/layout/FlexPort';
import VSBox from 'components/elements/addons/layout/vsbox/VSBox';
import VSBoxContent from 'components/elements/addons/layout/vsbox/VSBoxContent';
import VSBoxHeader from 'components/elements/addons/layout/vsbox/VSBoxHeader';
import SearchPagination from 'components/elements/addons/search/SearchPagination';
import SearchTotal from 'components/elements/addons/search/SearchTotal';
import HowlerCard from 'components/elements/display/HowlerCard';
import HitBanner from 'components/elements/hit/HitBanner';
import HitCard from 'components/elements/hit/HitCard';
import { HitLayout } from 'components/elements/hit/HitLayout';
import useHitSelection from 'components/hooks/useHitSelection';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import type { Hit } from 'models/entities/generated/Hit';
import type { FC } from 'react';
import React, { memo, useCallback, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import { StorageKey } from 'utils/constants';
import BundleParentMenu from './BundleParentMenu';
import { BundleScroller } from './BundleScroller';
import HitContextMenu from './HitContextMenu';
import HitQuery from './HitQuery';
import QuerySettings from './QuerySettings';

const Item: FC<{
  hit: Hit;
  onClick: (event: React.MouseEvent<HTMLDivElement>, hit: Hit) => void;
}> = memo(({ hit, onClick }) => {
  const theme = useTheme();

  const selectedHits = useContextSelector(HitContext, ctx => ctx.selectedHits);

  const selected = useContextSelector(ParameterContext, ctx => ctx.selected);

  const layout = useContextSelector(HitSearchContext, ctx => ctx.layout);

  const checkMiddleClick = useCallback((e: React.MouseEvent<HTMLDivElement, MouseEvent>, id: string | number) => {
    if (e.button === 1) {
      window.open(`${window.origin}/hits/${id}`, '_blank');
      e.stopPropagation();
      e.preventDefault();
    }
  }, []);

  // Search result list item renderer.
  return (
    <Box
      id={hit.howler.id}
      onAuxClick={e => checkMiddleClick(e, hit.howler.id)}
      onClick={ev => onClick(ev, hit)}
      sx={[
        {
          mb: 2,
          cursor: 'pointer',
          '& span,p,h6': {
            cursor: 'text'
          },
          '& .MuiPaper-root': {
            border: '4px solid transparent',
            boxShadow: `0px 0px 0px 0px transparent`,
            transition: theme.transitions.create(['border-color', 'box-shadow'])
          },
          '& .MuiCardContent-root': {
            p: 1,
            pb: 1
          },
          '& .MuiCardContent-root:last-child': {
            paddingBottom: 'inherit' // prevents slight height variation on selected card.
          }
        },
        selectedHits.some(_hit => _hit.howler.id === hit.howler.id) && {
          '& .MuiPaper-root': { borderColor: grey[500], boxShadow: `0px 0px 5px 2px ${grey[500]}` }
        },
        selected === hit.howler.id && {
          '& .MuiPaper-root': {
            borderColor: 'primary.main',
            boxShadow: `0px 0px 5px 2px ${theme.palette.primary.main}`
          }
        }
      ]}
    >
      <HitCard id={hit.howler.id} layout={layout} />
    </Box>
  );
});

const SearchPane: FC = () => {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const routeParams = useParams();

  const selected = useContextSelector(ParameterContext, ctx => ctx.selected);
  const setSelected = useContextSelector(ParameterContext, ctx => ctx.setSelected);
  const query = useContextSelector(ParameterContext, ctx => ctx.query);
  const setOffset = useContextSelector(ParameterContext, ctx => ctx.setOffset);

  const displayType = useContextSelector(HitSearchContext, ctx => ctx.displayType);
  const setDisplayType = useContextSelector(HitSearchContext, ctx => ctx.setDisplayType);
  const triggerSearch = useContextSelector(HitSearchContext, ctx => ctx.search);
  const searching = useContextSelector(HitSearchContext, ctx => ctx.searching);
  const response = useContextSelector(HitSearchContext, ctx => ctx.response);
  const error = useContextSelector(HitSearchContext, ctx => ctx.error);
  const viewId = useContextSelector(HitSearchContext, ctx => ctx.viewId);

  const { onClick } = useHitSelection();

  const getHit = useContextSelector(HitContext, ctx => ctx.getHit);
  const clearSelectedHits = useContextSelector(HitContext, ctx => ctx.clearSelectedHits);
  const bundleHit = useContextSelector(HitContext, ctx =>
    location.pathname.startsWith('/bundles') ? ctx.hits[routeParams.id] : null
  );

  const searchPaneWidth = useMyLocalStorageItem(StorageKey.SEARCH_PANE_WIDTH, null)[0];

  const verticalSorters = useMediaQuery('(max-width: 1919px)') || (searchPaneWidth ?? Number.MAX_SAFE_INTEGER) < 900;

  const selectedView = useContextSelector(ViewContext, ctx => ctx.views[viewId]);

  const getSelectedId = useCallback((event: React.MouseEvent<HTMLDivElement, MouseEvent>) => {
    const target = event.target as HTMLElement;
    const selectedElement = target.closest('[id]') as HTMLElement;

    if (!selectedElement) {
      return;
    }

    return selectedElement.id;
  }, []);

  useEffect(() => {
    if (location.pathname.startsWith('/bundles')) {
      getHit(routeParams.id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname, routeParams.id]);

  return (
    <FlexPort id="hitscrollbar">
      <PageCenter textAlign="left" mt={0} mb={6} ml={0} mr={0} maxWidth="1500px">
        <VSBox top={0}>
          <Stack ml={-1} mr={-1} sx={{ '& .overflowingContentWidgets > *': { zIndex: '2000 !important' } }} spacing={1}>
            {bundleHit && (
              <BundleScroller>
                <HitContextMenu getSelectedId={() => bundleHit.howler.id}>
                  <Stack spacing={1} sx={{ mx: -1 }}>
                    <HowlerCard
                      sx={[
                        { p: 1, border: '4px solid transparent', cursor: 'pointer' },
                        location.pathname.startsWith('/bundles') &&
                          selected === routeParams.id && { borderColor: 'primary.main' }
                      ]}
                      onClick={() => {
                        clearSelectedHits(bundleHit.howler.id);
                        setSelected(bundleHit.howler.id);
                      }}
                    >
                      <HitBanner hit={bundleHit} layout={HitLayout.DENSE} useListener />
                    </HowlerCard>
                  </Stack>
                </HitContextMenu>
              </BundleScroller>
            )}

            <Stack direction="row" spacing={1} alignItems="center">
              <Typography
                sx={{ color: 'text.secondary', fontSize: '0.9em', fontStyle: 'italic', mb: 0.5 }}
                variant="body2"
              >
                {t('hit.search.prompt')}
              </Typography>
              {error && (
                <Tooltip title={`${t('route.advanced.error')}: ${error}`}>
                  <ErrorOutline fontSize="small" color="error" />
                </Tooltip>
              )}
              <FlexOne />
              {bundleHit?.howler.bundles.length > 0 && <BundleParentMenu bundle={bundleHit} />}
              {bundleHit && (
                <Tooltip title={t('hit.bundle.close')}>
                  <IconButton size="small" onClick={() => navigate('/search')}>
                    <Close />
                  </IconButton>
                </Tooltip>
              )}
              <Tooltip title={t('route.views.save')}>
                <IconButton component={Link} disabled={!query} to={`/views/create?query=${query}`}>
                  <SavedSearch />
                </IconButton>
              </Tooltip>
              <Tooltip title={t('route.actions.save')}>
                <IconButton component={Link} disabled={!query} to={`/action/execute?query=${query}`}>
                  <Terminal />
                </IconButton>
              </Tooltip>
              <ToggleButtonGroup
                exclusive
                value={displayType}
                onChange={(__, value) => setDisplayType(value)}
                size="small"
              >
                <ToggleButton value="list">
                  <List />
                </ToggleButton>
                <ToggleButton value="grid">
                  <TableChart />
                </ToggleButton>
              </ToggleButtonGroup>
            </Stack>
          </Stack>

          <VSBoxHeader ml={-3} mr={-3} px={2} pb={1} sx={{ zIndex: 989 }}>
            <Stack sx={{ pt: 1 }}>
              <Stack sx={{ position: 'relative', flex: 1 }}>
                <HitQuery disabled={viewId && !selectedView} searching={searching} triggerSearch={triggerSearch} />
                {searching && (
                  <LinearProgress
                    sx={theme => ({
                      position: 'absolute',
                      left: 0,
                      right: 0,
                      bottom: 0,
                      borderBottomLeftRadius: theme.shape.borderRadius,
                      borderBottomRightRadius: theme.shape.borderRadius
                    })}
                  />
                )}
              </Stack>

              <QuerySettings verticalSorters={verticalSorters} boxSx={{ position: 'relative', pt: 1.5 }} />
            </Stack>

            {response && (
              <Stack direction="row" alignItems="center" sx={{ pt: 1 }}>
                <SearchTotal
                  total={response.total}
                  pageLength={response.items.length}
                  offset={response.offset}
                  sx={theme => ({ color: theme.palette.text.secondary, fontSize: '0.9em', fontStyle: 'italic' })}
                />
                <Box flex={1} />
                <SearchPagination
                  total={response.total}
                  limit={response.rows}
                  offset={response.offset}
                  onChange={nextOffset => setOffset(nextOffset)}
                />
              </Stack>
            )}
          </VSBoxHeader>
          <VSBoxContent mr={-1} ml={-1} mt={1}>
            <HitContextMenu getSelectedId={getSelectedId}>
              {!response ? (
                <AppListEmpty />
              ) : (
                response.items.map(hit => <Item key={hit.howler.id} hit={hit} onClick={onClick} />)
              )}
            </HitContextMenu>
          </VSBoxContent>
        </VSBox>
      </PageCenter>
    </FlexPort>
  );
};

export default memo(SearchPane);
