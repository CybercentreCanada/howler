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
import { IconButton, Stack, Table, TableBody, TableCell, TableHead, TableRow } from '@mui/material';
import useMatchers from 'components/app/hooks/useMatchers';
import { GridColumnsContext } from 'components/app/providers/GridColumnsProvider';
import ColumnHeader from 'components/elements/hit/grid/ColumnHeader';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import type { Hit } from 'models/entities/generated/Hit';
import type { WithMetadata } from 'models/WithMetadata';
import React, { useCallback, useContext, useEffect, useRef, useState, type PropsWithChildren } from 'react';
import { StorageKey } from 'utils/constants';
import HitRow from './HitRow';

const HitTable = ({
  query,
  items,
  refreshItems,
  ContextMenu,
  contextMenuProps,
  onItemClick
}: {
  query: string;
  items?: WithMetadata<Hit>[];
  refreshItems?: (query: string, append?: boolean) => void;
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
  const [analyticIds, setAnalyticIds] = useState<Record<string, string>>({});
  const { columns, columnWidths, columnSources, setColumnWidth, setColumns, isReady } = useContext(GridColumnsContext);

  const resizingCol = useRef<{ col: string; width: number; element: HTMLElement }>();

  useEffect(() => {
    items?.forEach(hit => {
      if (!analyticIds[hit.howler.analytic]) {
        getMatchingAnalytic(hit).then(_analytic => {
          if (_analytic) {
            setAnalyticIds(_analyticIds => ({ ..._analyticIds, [hit.howler.analytic]: _analytic.analytic_id }));
          }
        });
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analyticIds, items]);

  const onMouseMove = useCallback((event: MouseEvent) => {
    event.stopPropagation();
    event.preventDefault();

    const { col, width } = resizingCol.current;
    const newWidth = width + event.movementX;

    document.querySelectorAll<HTMLElement>(`.col-${col.replaceAll('.', '-')}`).forEach(el => {
      el.style.maxWidth = newWidth + 'px';
      el.style.width = newWidth + 'px';
    });

    resizingCol.current.width = newWidth;
  }, []);

  const onMouseUp = useCallback(() => {
    const { col, width, element } = resizingCol.current;

    if (isReady) {
      setColumnWidth(col, Math.round(width));
    }

    element.style.width = null;
    element.style.maxWidth = null;

    document.querySelectorAll<HTMLElement>(`.col-${col.replaceAll('.', '-')}`).forEach(el => {
      el.style.maxWidth = null;
      el.style.width = null;
    });

    window.removeEventListener('mousemove', onMouseMove);
    window.removeEventListener('mouseup', onMouseUp);
  }, [onMouseMove, setColumnWidth, isReady]);

  const onMouseDown = useCallback(
    (col: string, event: React.MouseEvent<HTMLElement, MouseEvent>) => {
      event.stopPropagation();
      event.preventDefault();

      const element = (event.target as HTMLElement).parentElement;
      const rect = element.getBoundingClientRect();

      resizingCol.current = { col, width: rect.width, element };

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

        if (isReady) {
          setColumns(arrayMove(columns, oldIndex, newIndex));
        }
      }
    },
    [columns, setColumns, isReady]
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
                  colSource={columnSources[col]}
                  onMouseDown={onMouseDown}
                  setColumns={isReady ? setColumns : () => null}
                />
              ))}
            </SortableContext>
          </DndContext>
          <TableCell sx={{ width: '100%' }} />
        </TableRow>
      </TableHead>
      {ContextMenu ? (
        <ContextMenu {...contextMenuProps}>{tableContent}</ContextMenu>
      ) : (
        <TableBody>{tableContent}</TableBody>
      )}
    </Table>
  );
};

export default HitTable;
