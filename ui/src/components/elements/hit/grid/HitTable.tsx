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
import { FormatIndentDecrease, FormatIndentIncrease, Search } from '@mui/icons-material';
import { IconButton, Stack, Table, TableCell, TableHead, TableRow } from '@mui/material';
import useMatchers from 'components/app/hooks/useMatchers';
import ColumnHeader from 'components/elements/hit/grid/ColumnHeader';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import type { Hit } from 'models/entities/generated/Hit';
import type { WithMetadata } from 'models/WithMetadata';
import React, { useCallback, useEffect, useRef, useState, type PropsWithChildren } from 'react';
import { StorageKey } from 'utils/constants';
import HitRow from './HitRow';

const HitTable = ({
  query,
  items,
  refreshItems,
  columns,
  onColumnChange,
  ContextMenu,
  contextMenuProps,
  onItemClick
}: {
  query: string;
  items?: WithMetadata<Hit>[];
  refreshItems?: (query: string, append?: boolean) => void;
  columns: string[];
  onColumnChange: (columns: string[]) => void;
  ContextMenu?: React.FC<PropsWithChildren<object>>;
  contextMenuProps?: object;
  onItemClick?: (event: React.MouseEvent<HTMLDivElement, MouseEvent>, hit: Hit) => void;
}) => {
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );
  const { getMatchingAnalytic } = useMatchers();

  const [collapseMainColumn, setCollapseMainColumn] = useMyLocalStorageItem(StorageKey.GRID_COLLAPSE_COLUMN, false);
  const [columnWidths, setColumnWidths] = useMyLocalStorageItem<Record<string, string>>(
    StorageKey.GRID_COLUMN_WIDTHS,
    {}
  );
  const [analyticIds, setAnalyticIds] = useState<Record<string, string>>({});

  const resizingCol = useRef<[string, HTMLElement]>();

  useEffect(() => {
    items?.forEach(hit => {
      if (!analyticIds[hit.howler.analytic]) {
        getMatchingAnalytic(hit).then(_analytic =>
          setAnalyticIds(_analyticIds => ({ ..._analyticIds, [hit.howler.analytic]: _analytic.analytic_id }))
        );
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analyticIds, items]);

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

    setColumnWidths({
      ...columnWidths,
      [col]: element.style.width
    });

    element.style.width = null;
    element.style.maxWidth = null;

    document.querySelectorAll<HTMLElement>(`.col-${col.replaceAll('.', '-')}`).forEach(el => {
      el.style.maxWidth = null;
      el.style.width = null;
    });

    window.removeEventListener('mousemove', onMouseMove);
    window.removeEventListener('mouseup', onMouseUp);
  }, [columnWidths, onMouseMove, setColumnWidths]);

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

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;

      if (over && active.id !== over.id) {
        const oldIndex = (columns ?? []).findIndex(entry => entry === active.id);
        const newIndex = (columns ?? []).findIndex(entry => entry === over.id);

        onColumnChange(arrayMove(columns, oldIndex, newIndex));
      }
    },
    [columns, onColumnChange]
  );

  const tableContent = (
    <>
      {items?.map(hit => (
        <HitRow
          key={hit.howler.id}
          hit={hit}
          analyticIds={analyticIds}
          columns={columns}
          columnWidths={columnWidths}
          collapseMainColumn={collapseMainColumn}
          onClick={onItemClick ? onItemClick : (_ev, _hit) => null}
        />
      ))}
      {refreshItems && (
        <TableRow>
          <TableCell colSpan={columns.length + 2}>
            <Stack alignItems="center" justifyContent="center" py={0.5} px={1}>
              <IconButton onClick={() => refreshItems(query, true)}>
                <Search />
              </IconButton>
            </Stack>
          </TableCell>
        </TableRow>
      )}
    </>
  );

  return (
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
                  setColumns={onColumnChange}
                />
              ))}
            </SortableContext>
          </DndContext>
          <TableCell sx={{ width: '100%' }} />
        </TableRow>
      </TableHead>
      {ContextMenu ? <ContextMenu {...contextMenuProps}>{tableContent}</ContextMenu> : tableContent}
    </Table>
  );
};

export default HitTable;
