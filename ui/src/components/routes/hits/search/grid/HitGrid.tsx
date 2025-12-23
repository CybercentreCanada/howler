import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  pointerWithin,
  useSensor,
  useSensors,
  type DragEndEvent
} from '@dnd-kit/core';
import { arrayMove, SortableContext, sortableKeyboardCoordinates } from '@dnd-kit/sortable';
import { Add, FormatIndentDecrease, FormatIndentIncrease, Info, List, Search, TableChart } from '@mui/icons-material';
import {
  IconButton,
  LinearProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
  useTheme
} from '@mui/material';
import useMatchers from 'components/app/hooks/useMatchers';
import { HitContext } from 'components/app/providers/HitProvider';
import { HitSearchContext } from 'components/app/providers/HitSearchProvider';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import { ViewContext } from 'components/app/providers/ViewProvider';
import FlexOne from 'components/elements/addons/layout/FlexOne';
import SearchTotal from 'components/elements/addons/search/SearchTotal';
import DevelopmentBanner from 'components/elements/display/features/DevelopmentBanner';
import DevelopmentIcon from 'components/elements/display/features/DevelopmentIcon';
import useHitSelection from 'components/hooks/useHitSelection';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import { useCallback, useEffect, useMemo, useRef, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useContextSelector } from 'use-context-selector';
import { StorageKey } from 'utils/constants';
import HitContextMenu from '../HitContextMenu';
import HitQuery from '../HitQuery';
import QuerySettings from '../QuerySettings';
import AddColumnModal from './AddColumnModal';
import ColumnHeader from './ColumnHeader';
import HitRow from './HitRow';

const HitGrid: FC = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );
  const { onClick } = useHitSelection();
  const { getMatchingAnalytic } = useMatchers();

  const search = useContextSelector(HitSearchContext, ctx => ctx.search);
  const displayType = useContextSelector(HitSearchContext, ctx => ctx.displayType);
  const setDisplayType = useContextSelector(HitSearchContext, ctx => ctx.setDisplayType);
  const response = useContextSelector(HitSearchContext, ctx => ctx.response);
  const searching = useContextSelector(HitSearchContext, ctx => ctx.searching);
  const viewId = useContextSelector(HitSearchContext, ctx => ctx.viewId);

  const selectedHits = useContextSelector(HitContext, ctx => ctx.selectedHits);

  const query = useContextSelector(ParameterContext, ctx => ctx.query);
  const selected = useContextSelector(ParameterContext, ctx => ctx.selected);

  const selectedView = useContextSelector(ViewContext, ctx => ctx.views[viewId]);

  const [collapseMainColumn, setCollapseMainColumn] = useMyLocalStorageItem(StorageKey.GRID_COLLAPSE_COLUMN, false);
  const [analyticIds, setAnalyticIds] = useState<Record<string, string>>({});

  const columnModalRef = useRef<HTMLButtonElement>();

  const [columns, setColumns] = useState<string[]>([
    'howler.outline.threat',
    'howler.outline.target',
    'howler.outline.indicators',
    'howler.outline.summary'
  ]);

  const [columnWidths, setColumnWidths] = useState<Record<string, string>>({});
  const [showAddColumn, setShowAddColumn] = useState(false);

  const resizingCol = useRef<[string, HTMLElement]>();

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
    response?.items.forEach(hit => {
      if (!analyticIds[hit.howler.analytic]) {
        getMatchingAnalytic(hit).then(_analytic =>
          setAnalyticIds(_analyticIds => ({ ..._analyticIds, [hit.howler.analytic]: _analytic.analytic_id }))
        );
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analyticIds, response]);

  const onMouseMove = useCallback((event: MouseEvent) => {
    event.stopPropagation();
    event.preventDefault();

    const [col, element] = resizingCol.current;
    const rect = element.getBoundingClientRect();

    document.querySelectorAll<HTMLElement>(`.col-${col.replaceAll('.', '-')}`).forEach(el => {
      el.style.maxWidth = rect.width + event.movementX + 'px';
      el.style.width = rect.width + event.movementX + 'px';
    });
  }, []);

  const onMouseUp = useCallback(() => {
    const [col, element] = resizingCol.current;

    setColumnWidths(_widths => ({
      ..._widths,
      [col]: element.style.width
    }));

    element.style.width = null;
    element.style.maxWidth = null;

    document.querySelectorAll<HTMLElement>(`.col-${col.replaceAll('.', '-')}`).forEach(el => {
      el.style.maxWidth = null;
      el.style.width = null;
    });

    window.removeEventListener('mousemove', onMouseMove);
    window.removeEventListener('mouseup', onMouseUp);
  }, [onMouseMove]);

  const onMouseDown = useCallback(
    (col: string, event: React.MouseEvent<HTMLElement, MouseEvent>) => {
      event.stopPropagation();
      event.preventDefault();

      resizingCol.current = [col, (event.target as HTMLElement).parentElement];

      window.addEventListener('mousemove', onMouseMove);
      window.addEventListener('mouseup', onMouseUp);
    },
    [onMouseMove, onMouseUp]
  );

  const onScroll = useCallback(
    (event: React.UIEvent<HTMLDivElement, UIEvent>) => {
      const target = event.target as HTMLDivElement;

      if (target.scrollHeight - target.scrollTop === target.clientHeight) {
        search(query, true);
      }
    },
    [query, search]
  );

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;

      if (active.id !== over.id) {
        const oldIndex = (columns ?? []).findIndex(entry => entry === active.id);
        const newIndex = (columns ?? []).findIndex(entry => entry === over.id);

        setColumns(arrayMove(columns, oldIndex, newIndex));
      }
    },
    [columns]
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
        <DevelopmentIcon />
      </Stack>
      <Stack direction="row" spacing={1}>
        <Stack position="relative" flex={1}>
          <HitQuery disabled={viewId && !selectedView} searching={searching} triggerSearch={search} compact />
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
        <ToggleButtonGroup exclusive value={displayType} onChange={(__, value) => setDisplayType(value)} size="small">
          <ToggleButton value="list">
            <List />
          </ToggleButton>
          <ToggleButton value="grid">
            <TableChart />
          </ToggleButton>
        </ToggleButtonGroup>
      </Stack>
      <Stack direction="row" spacing={1} width="100%" sx={{ '& > *': { flex: 1 } }}>
        <QuerySettings />
        {response && (
          <SearchTotal
            sx={{ alignSelf: 'center' }}
            color="text.secondary"
            offset={response.offset}
            pageLength={response.rows}
            total={response.total}
          />
        )}
        <Stack direction="row">
          <FlexOne />
          <IconButton ref={columnModalRef} onClick={() => setShowAddColumn(true)}>
            <Add fontSize="small" />
          </IconButton>
        </Stack>
        <AddColumnModal
          anchorEl={columnModalRef.current}
          open={showAddColumn}
          onClose={() => setShowAddColumn(false)}
          columns={columns}
          addColumn={key => setColumns(_columns => [..._columns, key])}
        />
      </Stack>
      <Stack
        component={Paper}
        spacing={1}
        width="100%"
        height="100%"
        sx={{ overflow: 'auto', flex: 1 }}
        onScroll={onScroll}
      >
        <Table sx={{ '& td,th': { px: 1, py: 0.25, whiteSpace: 'nowrap' } }}>
          <TableHead>
            <TableRow>
              <TableCell
                sx={{
                  borderRight: 'thin solid',
                  borderRightColor: 'divider'
                }}
              >
                <IconButton onClick={() => setCollapseMainColumn(!collapseMainColumn)}>
                  {collapseMainColumn ? (
                    <FormatIndentIncrease fontSize="small" />
                  ) : (
                    <FormatIndentDecrease fontSize="small" />
                  )}
                </IconButton>
              </TableCell>
              <DndContext sensors={sensors} collisionDetection={pointerWithin} onDragEnd={handleDragEnd}>
                <SortableContext items={columns}>
                  {columns.map(col => (
                    <ColumnHeader
                      key={col}
                      col={col}
                      width={columnWidths[col]}
                      onMouseDown={onMouseDown}
                      setColumns={setColumns}
                    />
                  ))}
                </SortableContext>
              </DndContext>
              <TableCell sx={{ width: '100%' }} />
            </TableRow>
          </TableHead>
          <HitContextMenu Component={TableBody} getSelectedId={getSelectedId}>
            {response?.items.map(hit => (
              <HitRow
                key={hit.howler.id}
                hit={hit}
                analyticIds={analyticIds}
                columns={columns}
                columnWidths={columnWidths}
                collapseMainColumn={collapseMainColumn}
                onClick={onClick}
              />
            ))}
            <TableRow>
              <TableCell colSpan={columns.length + 2}>
                <Stack alignItems="center" justifyContent="center" py={0.5} px={1}>
                  <IconButton onClick={() => search(query, true)}>
                    <Search />
                  </IconButton>
                </Stack>
              </TableCell>
            </TableRow>
          </HitContextMenu>
        </Table>

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
