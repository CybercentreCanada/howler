import { render, screen, waitFor } from '@testing-library/react';
import type { Case } from 'models/entities/generated/Case';
import type { Item } from 'models/entities/generated/Item';
import { act } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { setupContextSelectorMock } from 'tests/mocks';
import { createMockCase } from 'tests/utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

setupContextSelectorMock();

// ---------------------------------------------------------------------------
// Hoisted mocks
// ---------------------------------------------------------------------------

const mockDragEndHandler = vi.hoisted(() => ({ current: null as ((e: any) => void) | null }));
const mockDragStartHandler = vi.hoisted(() => ({ current: null as ((e: any) => void) | null }));
const mockActiveDrag = vi.hoisted(() => ({ current: null as any }));

vi.mock('@dnd-kit/core', () => ({
  DndContext: ({ children, onDragEnd, onDragStart }: any) => {
    mockDragEndHandler.current = onDragEnd;
    mockDragStartHandler.current = onDragStart;
    return <div id="dnd-context">{children}</div>;
  },
  DragOverlay: ({ children }: any) => <div id="drag-overlay">{children ?? null}</div>,
  MouseSensor: class {},
  TouchSensor: class {},
  useSensor: vi.fn(),
  useSensors: vi.fn(() => []),
  useDndContext: vi.fn(() => ({ active: mockActiveDrag.current })),
  useDroppable: vi.fn(() => ({ setNodeRef: vi.fn(), isOver: false })),
  useDraggable: vi.fn(() => ({
    attributes: {},
    listeners: {},
    setNodeRef: vi.fn(),
    transform: null,
    isDragging: false,
    active: null
  })),
  pointerWithin: vi.fn()
}));

vi.mock('@dnd-kit/utilities', () => ({
  CSS: { Transform: { toString: () => '' } }
}));

const mockDispatchApi = vi.hoisted(() => vi.fn());

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

const mockPut = vi.hoisted(() => vi.fn());

vi.mock('api', () => ({
  default: {
    v2: {
      case: {
        put: (...args: any[]) => mockPut(...args),
        get: vi.fn(),
        items: { del: vi.fn(), patch: vi.fn() }
      }
    }
  }
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    Link: ({ to, children, ...props }: any) => (
      <a href={to} {...props}>
        {children}
      </a>
    ),
    useLocation: vi.fn(() => ({ pathname: '/', search: '' }))
  };
});

// Stub heavy child components
vi.mock('./sidebar/CaseFolder', () => ({
  default: () => <div id="case-folder" />
}));

vi.mock('./sidebar/FolderEntry', () => ({
  default: ({ label }: any) => <div id="folder-entry-overlay">{label}</div>
}));

vi.mock('./sidebar/RootDropZone', () => ({
  default: ({ caseId }: any) => <div id="root-drop-zone" data-case-id={caseId} />
}));

vi.mock('components/app/providers/ModalProvider', async () => {
  const { createContext } = await import('react');
  return {
    ModalContext: createContext({ showModal: vi.fn(), close: vi.fn(), setContent: vi.fn() })
  };
});

vi.mock('components/app/providers/RecordProvider', async () => {
  const { createContext } = await import('react');
  return { RecordContext: createContext({ records: {} }) };
});

// ---------------------------------------------------------------------------
// Imports after mocks
// ---------------------------------------------------------------------------

import CaseSidebar from './CaseSidebar';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const hitItem = (path: string, value = path): Item => ({ type: 'hit', value, path });

const renderSidebar = (overrides?: Partial<Case>, onUpdate = vi.fn()) => {
  const _case = createMockCase({ case_id: 'case-1', items: [], ...overrides });
  render(
    <MemoryRouter>
      <CaseSidebar case={_case} update={onUpdate} />
    </MemoryRouter>
  );
  return { _case, onUpdate };
};

const fireDragStart = (data: object) => {
  act(() => {
    mockDragStartHandler.current?.({ active: { data: { current: data } } });
  });
};

const fireDragEnd = (activeData: object, overData: object) => {
  act(() => {
    mockDragEndHandler.current?.({
      active: { data: { current: activeData } },
      over: { data: { current: overData } }
    });
  });
};

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  mockDispatchApi.mockReset();
  mockPut.mockReset();
  mockActiveDrag.current = null;
  mockDragEndHandler.current = null;
  mockDragStartHandler.current = null;
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('CaseSidebar', () => {
  describe('structure', () => {
    it('renders the DndContext', () => {
      renderSidebar();
      expect(screen.getByTestId('dnd-context')).toBeInTheDocument();
    });

    it('renders the CaseFolder inside DndContext', () => {
      renderSidebar();
      expect(screen.getByTestId('case-folder')).toBeInTheDocument();
    });

    it('renders the RootDropZone with the correct caseId', () => {
      renderSidebar();
      expect(screen.getByTestId('root-drop-zone')).toHaveAttribute('data-case-id', 'case-1');
    });

    it('renders the DragOverlay', () => {
      renderSidebar();
      expect(screen.getByTestId('drag-overlay')).toBeInTheDocument();
    });
  });

  describe('drag overlay', () => {
    it('shows nothing in the overlay when no drag is active', () => {
      renderSidebar();
      expect(screen.queryByTestId('folder-entry-overlay')).not.toBeInTheDocument();
    });

    it('shows a FolderEntry in the overlay after drag starts', () => {
      renderSidebar();
      fireDragStart({ type: 'hit', label: 'my-item', entry: hitItem('folder/my-item'), caseId: 'case-1' });
      expect(screen.getByTestId('folder-entry-overlay')).toBeInTheDocument();
      expect(screen.getByText('my-item')).toBeInTheDocument();
    });

    it('clears the overlay after drag ends', async () => {
      const items = [hitItem('folder/my-item', 'val')];
      renderSidebar({ items });

      mockDispatchApi.mockResolvedValue(createMockCase({ case_id: 'case-1', items }));
      mockPut.mockReturnValue(Promise.resolve());

      fireDragStart({ type: 'hit', label: 'my-item', entry: hitItem('folder/my-item'), caseId: 'case-1' });
      expect(screen.getByTestId('folder-entry-overlay')).toBeInTheDocument();

      fireDragEnd(
        { type: 'hit', entry: hitItem('folder/my-item', 'val'), caseId: 'case-1' },
        { path: 'other', caseId: 'case-1' }
      );

      await waitFor(() => {
        expect(screen.queryByTestId('folder-entry-overlay')).not.toBeInTheDocument();
      });
    });
  });

  describe('handleDragEnd — item moves', () => {
    it('calls PUT with the updated path when a hit is moved to a folder', async () => {
      const items = [hitItem('docs/report', 'rep-val')];
      const updatedCase = createMockCase({ case_id: 'case-1', items: [hitItem('archive/report', 'rep-val')] });
      mockPut.mockReturnValue(Promise.resolve(updatedCase));
      mockDispatchApi.mockImplementation((p: Promise<any>) => p);

      const { onUpdate } = renderSidebar({ items });

      fireDragEnd(
        { type: 'hit', entry: hitItem('docs/report', 'rep-val'), caseId: 'case-1' },
        { path: 'archive', caseId: 'case-1' }
      );

      await waitFor(() => {
        expect(mockPut).toHaveBeenCalledWith(
          'case-1',
          expect.objectContaining({
            items: expect.arrayContaining([expect.objectContaining({ path: 'archive/report' })])
          })
        );
        expect(onUpdate).toHaveBeenCalledWith(updatedCase);
      });
    });

    it('moves an item to root when the over path is empty', async () => {
      const items = [hitItem('folder/report', 'rep-val')];
      const updatedCase = createMockCase({ case_id: 'case-1', items: [hitItem('report', 'rep-val')] });
      mockPut.mockReturnValue(Promise.resolve(updatedCase));
      mockDispatchApi.mockImplementation((p: Promise<any>) => p);

      const { onUpdate } = renderSidebar({ items });

      fireDragEnd(
        { type: 'hit', entry: hitItem('folder/report', 'rep-val'), caseId: 'case-1' },
        { path: '', caseId: 'case-1' } // root drop zone
      );

      await waitFor(() => {
        expect(mockPut).toHaveBeenCalledWith(
          'case-1',
          expect.objectContaining({
            items: expect.arrayContaining([expect.objectContaining({ path: 'report' })])
          })
        );
        expect(onUpdate).toHaveBeenCalledWith(updatedCase);
      });
    });

    it('moves all items under a folder when type is folder', async () => {
      const items = [hitItem('docs/a', 'a-val'), hitItem('docs/b', 'b-val'), hitItem('other/c', 'c-val')];
      const updatedCase = createMockCase({ case_id: 'case-1', items });
      mockPut.mockReturnValue(Promise.resolve(updatedCase));
      mockDispatchApi.mockImplementation((p: Promise<any>) => p);

      renderSidebar({ items });

      fireDragEnd({ type: 'folder', entry: { path: 'docs' }, caseId: 'case-1' }, { path: 'archive', caseId: 'case-1' });

      await waitFor(() => {
        expect(mockPut).toHaveBeenCalledWith(
          'case-1',
          expect.objectContaining({
            items: expect.arrayContaining([
              expect.objectContaining({ path: 'archive/docs/a' }),
              expect.objectContaining({ path: 'archive/docs/b' }),
              // Items not under 'docs' are unchanged
              expect.objectContaining({ path: 'other/c' })
            ])
          })
        );
      });
    });
  });

  describe('handleDragEnd — guards', () => {
    it('does nothing when over is null', async () => {
      renderSidebar({ items: [hitItem('folder/item', 'val')] });

      act(() => {
        mockDragEndHandler.current?.({
          active: { data: { current: { type: 'hit', entry: hitItem('folder/item', 'val'), caseId: 'case-1' } } },
          over: null
        });
      });

      await new Promise(r => setTimeout(r, 0));
      expect(mockPut).not.toHaveBeenCalled();
    });

    it('does nothing when the path would not change (no-op drop)', async () => {
      const items = [hitItem('folder/item', 'val')];
      renderSidebar({ items });

      // Dropping into the same folder → same path
      fireDragEnd(
        { type: 'hit', entry: hitItem('folder/item', 'val'), caseId: 'case-1' },
        { path: 'folder', caseId: 'case-1' }
      );

      await new Promise(r => setTimeout(r, 0));
      expect(mockPut).not.toHaveBeenCalled();
    });

    it('does nothing when movingEntry.path is missing', async () => {
      renderSidebar();

      fireDragEnd(
        { type: 'hit', entry: { value: 'val' }, caseId: 'case-1' }, // no path
        { path: 'archive', caseId: 'case-1' }
      );

      await new Promise(r => setTimeout(r, 0));
      expect(mockPut).not.toHaveBeenCalled();
    });
  });
});
