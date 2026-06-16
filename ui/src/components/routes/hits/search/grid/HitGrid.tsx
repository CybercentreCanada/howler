import { Info } from '@mui/icons-material';
import { LinearProgress, Paper, Stack, TableBody, Typography, useTheme } from '@mui/material';
import { GridColumnsContext } from 'components/app/providers/GridColumnsProvider';
import { HitContext } from 'components/app/providers/HitProvider';
import { HitSearchContext } from 'components/app/providers/HitSearchProvider';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import SearchTotal from 'components/elements/addons/search/SearchTotal';
import DevelopmentBanner from 'components/elements/display/features/DevelopmentBanner';
import AddColumnModal from 'components/elements/hit/grid/AddColumnModal';
import HitTable from 'components/elements/hit/grid/HitTable';
import HitContextMenu from 'components/elements/hit/HitContextMenu';
import useHitSelection from 'components/hooks/useHitSelection';
import { uniq } from 'lodash-es';
import { useCallback, useContext, useMemo, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useContextSelector } from 'use-context-selector';
import HitQuery from '../HitQuery';
import QuerySettings from '../QuerySettings';
import SearchActionMenu from '../shared/SearchActionMenu';

const HitGrid: FC = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  const { onClick } = useHitSelection();

  const search = useContextSelector(HitSearchContext, ctx => ctx.search);
  const response = useContextSelector(HitSearchContext, ctx => ctx.response);
  const searching = useContextSelector(HitSearchContext, ctx => ctx.searching);

  const selectedHits = useContextSelector(HitContext, ctx => ctx.selectedHits);

  const query = useContextSelector(ParameterContext, ctx => ctx.query);
  const selected = useContextSelector(ParameterContext, ctx => ctx.selected);

  const { columns, setColumns } = useContext(GridColumnsContext);

  const showSelectBar = useMemo(() => {
    if (selectedHits.length > 1) {
      return true;
    }

    if (selectedHits.length === 1 && selected && selectedHits[0]?.howler.id !== selected) {
      return true;
    }

    return false;
  }, [selected, selectedHits]);

  const onScroll = useCallback(
    (event: React.UIEvent<HTMLDivElement, UIEvent>) => {
      const target = event.target as HTMLDivElement;

      if (target.scrollHeight - target.scrollTop === target.clientHeight) {
        search(query, true);
      }
    },
    [query, search]
  );

  const getSelectedId = useCallback((event: React.MouseEvent<HTMLDivElement, MouseEvent>) => {
    const target = event.target as HTMLElement;
    const selectedElement = target.closest('[id]') as HTMLElement;

    if (!selectedElement) {
      return;
    }

    return selectedElement.id;
  }, []);

  return (
    <Stack
      spacing={1}
      p={2}
      width="100%"
      sx={{ overflow: 'hidden', height: `calc(100vh - ${theme.spacing(showSelectBar ? 13 : 8)})` }}
    >
      <DevelopmentBanner />
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Typography
          sx={{ color: 'text.secondary', fontSize: '0.9em', fontStyle: 'italic', mb: 0.5, textAlign: 'left' }}
          variant="body2"
        >
          {t('hit.search.prompt')}
        </Typography>
        <SearchActionMenu query={query} />
      </Stack>
      <Stack direction="row" spacing={1}>
        <Stack position="relative" flex={1}>
          <HitQuery searching={searching} triggerSearch={search} compact />
          {searching && (
            <LinearProgress
              sx={{
                position: 'absolute',
                left: 0,
                right: 0,
                bottom: 0,
                borderBottomLeftRadius: theme.shape.borderRadius,
                borderBottomRightRadius: theme.shape.borderRadius
              }}
            />
          )}
        </Stack>
      </Stack>
      <Stack direction="row" spacing={1} width="100%" alignItems="center">
        <QuerySettings boxSx={{ flex: 1 }} />
        <AddColumnModal columns={columns} addColumn={key => setColumns(uniq([...columns, key]))} />
      </Stack>
      {response && (
        <SearchTotal
          sx={{ color: 'text.secondary', fontSize: '0.9em', fontStyle: 'italic', mb: 0.5 }}
          variant="body2"
          offset={response.offset}
          pageLength={response.rows}
          total={response.total}
        />
      )}
      <Stack
        component={Paper}
        spacing={1}
        width="100%"
        height="100%"
        sx={{ overflow: 'auto', flex: 1 }}
        onScroll={onScroll}
      >
        <HitTable
          query={query}
          items={response?.items}
          refreshItems={search}
          ContextMenu={HitContextMenu}
          contextMenuProps={{ Component: TableBody, getSelectedId: getSelectedId }}
          onItemClick={onClick}
        />
        {(response?.total ?? 0) < 1 && (
          <Stack direction="row" spacing={1} alignItems="center" p={1} justifyContent="center" flex={1}>
            <Typography variant="h3" color="text.secondary" display="flex" flexDirection="row" alignItems="center">
              <Info fontSize="inherit" sx={{ color: 'text.secondary', mr: 1 }} />
              <span>{t('app.list.empty')}</span>
            </Typography>
          </Stack>
        )}
      </Stack>
    </Stack>
  );
};

export default HitGrid;
