import { ErrorOutline, SavedSearch, Terminal } from '@mui/icons-material';
import { Box, IconButton, LinearProgress, Stack, Tooltip, Typography, useMediaQuery, useTheme } from '@mui/material';
import { grey } from '@mui/material/colors';
import AppListEmpty from 'commons/components/display/AppListEmpty';
import PageCenter from 'commons/components/pages/PageCenter';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import { RecordContext } from 'components/app/providers/RecordProvider';
import { RecordSearchContext } from 'components/app/providers/RecordSearchProvider';
import FlexOne from 'components/elements/addons/layout/FlexOne';
import FlexPort from 'components/elements/addons/layout/FlexPort';
import VSBox from 'components/elements/addons/layout/vsbox/VSBox';
import VSBoxContent from 'components/elements/addons/layout/vsbox/VSBoxContent';
import VSBoxHeader from 'components/elements/addons/layout/vsbox/VSBoxHeader';
import SearchPagination from 'components/elements/addons/search/SearchPagination';
import SearchTotal from 'components/elements/addons/search/SearchTotal';
import HitCard from 'components/elements/hit/HitCard';
import { HitLayout } from 'components/elements/hit/HitLayout';
import ObservableCard from 'components/elements/observable/ObservableCard';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import useRecordSelection from 'components/hooks/useRecordSelection';
import type { Hit } from 'models/entities/generated/Hit';
import type { Observable } from 'models/entities/generated/Observable';
import type { FC } from 'react';
import React, { memo, useCallback, useMemo } from 'react';
import { isMobile } from 'react-device-detect';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import { StorageKey } from 'utils/constants';
import { isHit, isObservable } from 'utils/typeUtils';
import LayoutSettings from './LayoutSettings';
import QuerySettings from './QuerySettings';
import RecordContextMenu from './RecordContextMenu';
import RecordQuery from './RecordQuery';

const Item: FC<{
  record: Hit | Observable;
  onClick: (event: React.MouseEvent<HTMLDivElement>, record: Hit | Observable) => void;
}> = memo(({ record, onClick }) => {
  const theme = useTheme();

  const selectedRecords = useContextSelector(RecordContext, ctx => ctx.selectedRecords);

  const selected = useContextSelector(ParameterContext, ctx => ctx.selected);

  const checkMiddleClick = useCallback((e: React.MouseEvent<HTMLDivElement, MouseEvent>, id: string | number) => {
    if (e.button === 1) {
      window.open(`${window.origin}/hits/${id}`, '_blank');
      e.stopPropagation();
      e.preventDefault();
    }
  }, []);

  const [hitLayout] = useMyLocalStorageItem(StorageKey.HIT_LAYOUT, HitLayout.NORMAL);

  const layout: HitLayout = useMemo(() => (isMobile ? HitLayout.COMFY : hitLayout), [hitLayout]);

  // Search result list item renderer.
  return (
    <Box
      id={record.howler.id}
      onAuxClick={e => checkMiddleClick(e, record.howler.id)}
      onClick={ev => onClick(ev, record)}
      sx={[
        {
          mb: 2,
          cursor: 'pointer',
          '& span,p,h6': {
            cursor: 'text'
          },
          '& > .MuiPaper-root': {
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
        selectedRecords.some(_record => _record.howler.id === record.howler.id) && {
          '& > .MuiPaper-root': { borderColor: grey[500], boxShadow: `0px 0px 5px 2px ${grey[500]}` }
        },
        selected === record.howler.id && {
          '& > .MuiPaper-root': {
            borderColor: 'primary.main',
            boxShadow: `0px 0px 5px 2px ${theme.palette.primary.main}`
          }
        }
      ]}
    >
      {isHit(record) && <HitCard id={record.howler.id} layout={layout} />}
      {isObservable(record) && <ObservableCard id={record.howler.id} observable={record} />}
    </Box>
  );
});

const SearchPane: FC = () => {
  const { t } = useTranslation();

  const query = useContextSelector(ParameterContext, ctx => ctx.query);
  const setOffset = useContextSelector(ParameterContext, ctx => ctx.setOffset);

  const triggerSearch = useContextSelector(RecordSearchContext, ctx => ctx.search);
  const searching = useContextSelector(RecordSearchContext, ctx => ctx.searching);
  const response = useContextSelector(RecordSearchContext, ctx => ctx.response);
  const error = useContextSelector(RecordSearchContext, ctx => ctx.error);

  const { onClick } = useRecordSelection();

  const searchPaneWidth = useMyLocalStorageItem(StorageKey.SEARCH_PANE_WIDTH, null)[0];

  const verticalSorters = useMediaQuery('(max-width: 1919px)') || (searchPaneWidth ?? Number.MAX_SAFE_INTEGER) < 900;

  const getSelectedId = useCallback((event: React.MouseEvent<HTMLDivElement, MouseEvent>) => {
    const target = event.target as HTMLElement;
    const selectedElement = target.closest('[id]') as HTMLElement;

    if (!selectedElement) {
      return;
    }

    return selectedElement.id;
  }, []);

  return (
    <FlexPort id="hitscrollbar">
      <PageCenter textAlign="left" mt={0} mb={6} ml={0} mr={0} maxWidth="1500px">
        <VSBox top={0}>
          <Stack ml={-1} mr={-1} sx={{ '& .overflowingContentWidgets > *': { zIndex: '2000 !important' } }} spacing={1}>
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
              <LayoutSettings />
            </Stack>
          </Stack>

          <VSBoxHeader ml={-3} mr={-3} px={2} pb={1} sx={{ zIndex: 989 }}>
            <Stack sx={{ pt: 1 }}>
              <Stack sx={{ position: 'relative', flex: 1 }}>
                <RecordQuery searching={searching} triggerSearch={triggerSearch} />
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
            <RecordContextMenu getSelectedId={getSelectedId}>
              {!response ? (
                <AppListEmpty />
              ) : (
                response.items.map(record => <Item key={record.howler.id} record={record} onClick={onClick} />)
              )}
            </RecordContextMenu>
          </VSBoxContent>
        </VSBox>
      </PageCenter>
    </FlexPort>
  );
};

export default memo(SearchPane);
