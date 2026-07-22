import { render, screen, waitFor } from '@testing-library/react';
import type { Case } from 'models/entities/generated/Case';
import type { Item } from 'models/entities/generated/Item';
import { act } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { setupContextSelectorMock } from 'tests/mocks';
import { createMockCase } from 'tests/utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

setupContextSelectorMock();

const mockDragEndHandler = vi.hoisted(() => ({ current: null as ((e: any) => void) | null }));
const mockDragStartHandler = vi.hoisted(() => ({ current: null as ((e: any) => void) | null }));

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
  pointerWithin: vi.fn()
}));

vi.mock('@dnd-kit/utilities', () => ({
  CSS: { Transform: { toString: () => '' } }
}));

const mockDispatchApi = vi.hoisted(() => vi.fn());

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

const mockItemsPut = vi.hoisted(() => vi.fn());

vi.mock('api', () => ({
  default: {
    v2: {
      case: {
        get: vi.fn(),
        items: {
          put: (...args: any[]) => mockItemsPut(...args),
          post: vi.fn(),
          del: vi.fn(),
          patch: vi.fn()
        }
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

import CaseSidebar from './CaseSidebar';

const hitItem = (value: string, id = value, parent: string | null = null): Item => ({
  type: 'hit',
  value,
  id,
  parent,
  name: null
});

const renderSidebar = (overrides?: Partial<Case>, onUpdate = vi.fn()) => {
  const _case = createMockCase({ case_id: 'case-1', items: [], ...overrides });
  const utils = render(
    <MemoryRouter>
      <CaseSidebar case={_case} update={onUpdate} />
    </MemoryRouter>
  );
  return { _case, onUpdate, ...utils };
};

const fireDragStart = (data: object) => {
  act(() => {
    mockDragStartHandler.current?.({ active: { data: { current: data } } });
  });
};

const fireDragEnd = (activeData: object, overData: object | null) => {
  act(() => {
    mockDragEndHandler.current?.({
      active: { data: { current: activeData } },
      over: overData ? { data: { current: overData } } : null
    });
  });
};

beforeEach(() => {
  mockDispatchApi.mockReset();
  mockItemsPut.mockReset();
  mockDragEndHandler.current = null;
  mockDragStartHandler.current = null;
});

describe('CaseSidebar', () => {
  it('renders navigation links and DnD wrappers', () => {
    const { container } = renderSidebar();
    expect(container.querySelector('#dnd-context')).toBeInTheDocument();
    expect(container.querySelector('#case-folder')).toBeInTheDocument();
    expect(container.querySelector('#drag-overlay')).toBeInTheDocument();
    expect(container.querySelector('#root-drop-zone')).toHaveAttribute('data-case-id', 'case-1');
    expect(screen.getByText('page.cases.dashboard').closest('a')).toHaveAttribute('href', '/cases/case-1');
  });

  it('shows and clears drag overlay label across drag start/end', async () => {
    const items = [hitItem('folder/my-item', 'val')];
    renderSidebar({ items });
    fireDragStart({ type: 'hit', label: 'my-item', entry: hitItem('folder/my-item', 'val'), caseId: 'case-1' });
    expect(screen.getByText('my-item')).toBeInTheDocument();

    mockItemsPut.mockReturnValue('put-request');
    mockDispatchApi.mockResolvedValue(createMockCase({ case_id: 'case-1', items }));

    fireDragEnd(
      { type: 'hit', entry: hitItem('folder/my-item', 'val', 'docs-folder'), caseId: 'case-1' },
      { folderId: 'archive-folder', caseId: 'case-1' }
    );

    await waitFor(() => {
      expect(screen.queryByText('my-item')).not.toBeInTheDocument();
    });
  });

  it('moves item to folder by calling items.put with parent folder id', async () => {
    const items = [hitItem('v', 'item-1', 'old-folder')];
    const updatedCase = createMockCase({ case_id: 'case-1', items });
    mockItemsPut.mockReturnValue('put-request');
    mockDispatchApi.mockResolvedValue(updatedCase);
    const { onUpdate } = renderSidebar({ items });

    fireDragEnd({ type: 'hit', entry: items[0], caseId: 'case-1' }, { folderId: 'archive-folder', caseId: 'case-1' });

    await waitFor(() => {
      expect(mockItemsPut).toHaveBeenCalledWith('case-1', 'item-1', { parent: 'archive-folder' });
      expect(onUpdate).toHaveBeenCalledWith(updatedCase);
    });
  });

  it('moves item to root with parent null', async () => {
    const items = [hitItem('v', 'item-1', 'folder-id')];
    mockItemsPut.mockReturnValue('put-request');
    mockDispatchApi.mockResolvedValue(createMockCase({ case_id: 'case-1', items }));
    renderSidebar({ items });

    fireDragEnd({ type: 'hit', entry: items[0], caseId: 'case-1' }, { caseId: 'case-1' });

    await waitFor(() => {
      expect(mockItemsPut).toHaveBeenCalledWith('case-1', 'item-1', { parent: null });
    });
  });

  it('does nothing for no-op drops (same parent) and invalid payloads', async () => {
    renderSidebar({ items: [hitItem('v', 'item-1', 'same-folder')] });

    fireDragEnd(
      { type: 'hit', entry: hitItem('v', 'item-1', 'same-folder'), caseId: 'case-1' },
      { folderId: 'same-folder', caseId: 'case-1' }
    );
    fireDragEnd({ type: 'hit', entry: { type: 'hit', value: 'v' }, caseId: 'case-1' }, { folderId: 'x' });
    fireDragEnd({ type: 'hit', entry: hitItem('v', 'id-2') }, null);

    await new Promise(resolve => setTimeout(resolve, 0));
    expect(mockItemsPut).not.toHaveBeenCalled();
  });
});
