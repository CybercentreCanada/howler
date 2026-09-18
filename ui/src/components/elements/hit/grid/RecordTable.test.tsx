/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const mockSetColumnWidth = vi.hoisted(() => vi.fn());
const mockSetColumns = vi.hoisted(() => vi.fn());
const mockGetMatchingAnalytic = vi.hoisted(() => vi.fn().mockResolvedValue({ analytic_id: 'analytic-1' }));
const gridColumnsContextToken = vi.hoisted(() => ({ name: 'grid-columns-context' }));

vi.mock('@dnd-kit/core', () => ({
  DndContext: ({ children, onDragEnd }: any) => (
    <div>
      <button onClick={() => onDragEnd({ active: { id: 'col1' }, over: { id: 'col2' } })}>drag-column</button>
      {children}
    </div>
  ),
  KeyboardSensor: vi.fn(),
  PointerSensor: vi.fn(),
  pointerWithin: vi.fn(),
  useSensor: vi.fn(),
  useSensors: vi.fn(() => [])
}));

vi.mock('@dnd-kit/sortable', () => ({
  SortableContext: ({ children }: any) => <div>{children}</div>,
  arrayMove: (items: string[], from: number, to: number) => {
    const next = [...items];
    const [moved] = next.splice(from, 1);
    next.splice(to, 0, moved);
    return next;
  },
  sortableKeyboardCoordinates: vi.fn()
}));

vi.mock('@mui/icons-material', () => ({
  FormatIndentDecrease: () => <div>collapse</div>,
  FormatIndentIncrease: () => <div>expand</div>,
  Search: () => <div>search-icon</div>
}));

vi.mock('@mui/material', () => ({
  IconButton: ({ children, onClick }: any) => <button onClick={onClick}>{children}</button>,
  Stack: ({ children }: any) => <div>{children}</div>,
  Table: ({ children }: any) => <div>{children}</div>,
  TableBody: ({ children }: any) => <div>{children}</div>,
  TableCell: ({ children }: any) => <div>{children}</div>,
  TableHead: ({ children }: any) => <div>{children}</div>,
  TableRow: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/app/hooks/useMatchers', () => ({
  default: () => ({ getMatchingAnalytic: mockGetMatchingAnalytic })
}));

vi.mock('components/app/providers/GridColumnsProvider', () => ({
  GridColumnsContext: gridColumnsContextToken
}));

vi.mock('components/hooks/useMyLocalStorage', () => ({
  useMyLocalStorageItem: () => [false, vi.fn()]
}));

vi.mock('utils/constants', () => ({
  StorageKey: { GRID_COLLAPSE_COLUMN: 'GRID_COLLAPSE_COLUMN' }
}));

vi.mock('utils/typeUtils', () => ({
  isHit: (record: any) => record?.__index === 'hit'
}));

vi.mock('./ColumnHeader', () => ({
  default: ({ col, onMouseDown }: any) => <button onMouseDown={e => onMouseDown(col, e)}>{col}</button>
}));

vi.mock('./RecordRow', () => ({
  default: ({ record, analyticIds }: any) => <div>{`row:${record.howler.id}:${analyticIds[record.howler.analytic] ?? ''}`}</div>
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === gridColumnsContextToken) {
        return {
          columns: ['col1', 'col2'],
          columnWidths: { col1: 120, col2: 80 },
          columnSources: { col1: 's1', col2: 's2' },
          setColumnWidth: mockSetColumnWidth,
          setColumns: mockSetColumns,
          isReady: true
        };
      }
      return actual.useContext(context);
    }
  };
});

import RecordTable from './RecordTable';

describe('RecordTable', () => {
  it('loads analytic ids, refreshes, reorders columns, and resizes columns', async () => {
    render(
      <RecordTable
        query="status:open"
        items={[{ __index: 'hit', howler: { id: 'hit-1', analytic: 'A' } } as any]}
        refreshItems={vi.fn()}
      />
    );

    await waitFor(() => expect(mockGetMatchingAnalytic).toHaveBeenCalled());
    expect(screen.getByText('row:hit-1:analytic-1')).toBeInTheDocument();

    fireEvent.click(screen.getByText('search-icon'));
    fireEvent.click(screen.getByText('drag-column'));
    expect(mockSetColumns).toHaveBeenCalledWith(['col2', 'col1']);

    const header = screen.getByText('col1');
    Object.defineProperty(header.parentElement, 'getBoundingClientRect', {
      value: () => ({ width: 120 })
    });
    fireEvent.mouseDown(header);
    fireEvent.mouseMove(window, { movementX: 20 });
    fireEvent.mouseUp(window);

    expect(mockSetColumnWidth).toHaveBeenCalledWith('col1', 140);
  });
});
