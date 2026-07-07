import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { Case } from 'models/entities/generated/Case';
import type { Item } from 'models/entities/generated/Item';
import { act } from 'react';
import { createMockCase } from 'tests/utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Tree } from './types';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('components/elements/ContextMenu', () => ({
  default: ({ items, children }: any) => (
    <div>
      {children}
      {items.map((item: any) => {
        if (item.kind === 'item') {
          return (
            <button key={item.id} id={item.id} onClick={item.onClick}>
              {item.label}
            </button>
          );
        }
        if (item.kind === 'divider') {
          return <hr key={item.id} />;
        }
        return null;
      })}
    </div>
  )
}));

const mockDispatchApi = vi.hoisted(() => vi.fn());

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

const mockDel = vi.hoisted(() => vi.fn());
const mockPatch = vi.hoisted(() => vi.fn());

vi.mock('api', () => ({
  default: {
    v2: {
      case: {
        items: {
          del: (...args: any[]) => mockDel(...args),
          patch: (...args: any[]) => mockPatch(...args)
        }
      }
    }
  }
}));

const mockShowModal = vi.hoisted(() => vi.fn());

vi.mock('components/app/providers/ModalProvider', async () => {
  const { createContext } = await import('react');
  return {
    ModalContext: createContext({ showModal: mockShowModal, close: vi.fn(), setContent: vi.fn() })
  };
});

vi.mock('components/routes/cases/modals/RenameItemModal', () => ({
  default: () => <div id="rename-item-modal" />
}));

// ---------------------------------------------------------------------------
// Imports (after mocks so that module registry picks up the stubs)
// ---------------------------------------------------------------------------

import CaseFolderContextMenu, { collectAllLeaves, getOpenUrl } from './CaseFolderContextMenu';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockCase: Case = createMockCase({ case_id: 'case-1' });

const hitLeaf: Item = { id: 'id-hit', type: 'hit', value: 'hit-123', name: 'hit-item' };
const referenceLeaf: Item = { id: 'id-ref', type: 'reference', value: 'https://example.com', name: 'ref-item' };
const eventLeaf: Item = { id: 'id-event', type: 'event', value: 'obs-456', name: 'event-item' };
const caseLeaf: Item = { id: 'id-case', type: 'case', value: 'nested-case-id', name: 'case-item' };
const tableLeaf: Item = { id: 'id-table', type: 'table', value: 'table-789', name: 'table-item' };
const leadLeaf: Item = { id: 'id-lead', type: 'lead', value: 'lead-999', name: 'lead-item' };

const renderMenu = (props: Partial<React.ComponentPropsWithoutRef<typeof CaseFolderContextMenu>>) =>
  render(
    <CaseFolderContextMenu _case={mockCase} {...props}>
      <div id="child">child</div>
    </CaseFolderContextMenu>
  );

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  mockDel.mockClear();
  mockPatch.mockClear();
  mockDispatchApi.mockClear();
  mockShowModal.mockClear();
  mockDispatchApi.mockImplementation((p: Promise<any>) => p);
  mockDel.mockResolvedValue(mockCase);
  mockPatch.mockResolvedValue(mockCase);
  vi.spyOn(window, 'open').mockReturnValue(null);
});

// ---------------------------------------------------------------------------
// Unit tests for exported utilities
// ---------------------------------------------------------------------------

describe('collectAllLeaves', () => {
  it('returns leaves at the root level', () => {
    const tree: Tree = { leaves: [hitLeaf, referenceLeaf] };
    expect(collectAllLeaves(tree)).toEqual([hitLeaf, referenceLeaf]);
  });

  it('returns leaves from nested subfolders', () => {
    const tree: Tree = {
      leaves: [hitLeaf],
      folders: {
        subfolder: { id: 'subfolder-id', leaves: [referenceLeaf] }
      }
    };
    expect(collectAllLeaves(tree)).toEqual([hitLeaf, referenceLeaf]);
  });

  it('returns leaves from deeply nested subfolders', () => {
    const tree: Tree = {
      leaves: [],
      folders: {
        level1: {
          id: 'level1-id',
          leaves: [hitLeaf],
          folders: {
            level2: { id: 'level2-id', leaves: [referenceLeaf] }
          }
        }
      }
    };
    const result = collectAllLeaves(tree);
    expect(result).toContain(hitLeaf);
    expect(result).toContain(referenceLeaf);
  });

  it('returns an empty array for an empty tree', () => {
    expect(collectAllLeaves({ leaves: [] })).toEqual([]);
  });
});

describe('getOpenUrl', () => {
  it('returns the value directly for a reference item', () => {
    expect(getOpenUrl(referenceLeaf)).toBe('https://example.com');
  });

  it('returns /hits/<id> for a hit item', () => {
    expect(getOpenUrl(hitLeaf)).toBe('/hits/hit-123');
  });

  it('returns /events/<id> for an event item', () => {
    expect(getOpenUrl(eventLeaf)).toBe('/events/obs-456');
  });

  it('returns /cases/<id> for a case item', () => {
    expect(getOpenUrl(caseLeaf)).toBe('/cases/nested-case-id');
  });

  it('returns null for a table item', () => {
    expect(getOpenUrl(tableLeaf)).toBeNull();
  });

  it('returns null for a lead item', () => {
    expect(getOpenUrl(leadLeaf)).toBeNull();
  });

  it('returns null when value is undefined', () => {
    expect(getOpenUrl({ type: 'hit' })).toBeNull();
  });

  it('returns null when type is undefined', () => {
    expect(getOpenUrl({ value: 'something' })).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Component tests
// ---------------------------------------------------------------------------

describe('CaseFolderContextMenu', () => {
  describe('renders children', () => {
    it('renders children content', () => {
      renderMenu({ leaf: hitLeaf });
      expect(screen.getByTestId('child')).toBeInTheDocument();
    });
  });

  describe('menu items for leaf types', () => {
    it('shows "Open item" and "Remove item" for a hit leaf', () => {
      renderMenu({ leaf: hitLeaf });
      expect(screen.getByTestId('open-item')).toBeInTheDocument();
      expect(screen.getByTestId('remove-item')).toBeInTheDocument();
    });

    it('shows "Open item" and "Remove item" for a reference leaf', () => {
      renderMenu({ leaf: referenceLeaf });
      expect(screen.getByTestId('open-item')).toBeInTheDocument();
      expect(screen.getByTestId('remove-item')).toBeInTheDocument();
    });

    it('shows "Open item" and "Remove item" for an event leaf', () => {
      renderMenu({ leaf: eventLeaf });
      expect(screen.getByTestId('open-item')).toBeInTheDocument();
      expect(screen.getByTestId('remove-item')).toBeInTheDocument();
    });

    it('shows "Open item" and "Remove item" for a case leaf', () => {
      renderMenu({ leaf: caseLeaf });
      expect(screen.getByTestId('open-item')).toBeInTheDocument();
      expect(screen.getByTestId('remove-item')).toBeInTheDocument();
    });

    it('shows only "Remove item" for a table leaf (no open URL)', () => {
      renderMenu({ leaf: tableLeaf });
      expect(screen.queryByTestId('open-item')).not.toBeInTheDocument();
      expect(screen.getByTestId('remove-item')).toBeInTheDocument();
    });

    it('shows only "Remove item" for a lead leaf (no open URL)', () => {
      renderMenu({ leaf: leadLeaf });
      expect(screen.queryByTestId('open-item')).not.toBeInTheDocument();
      expect(screen.getByTestId('remove-item')).toBeInTheDocument();
    });

    it('labels the remove button "Remove item" for a leaf', () => {
      renderMenu({ leaf: hitLeaf });
      expect(screen.getByTestId('remove-item')).toHaveTextContent('page.cases.sidebar.item.remove');
    });

    it('shows a divider for all leaf types (between leaf actions and remove)', () => {
      const { container: withOpen } = renderMenu({ leaf: hitLeaf });
      expect(withOpen.querySelector('hr')).not.toBeNull();

      const { container: withoutOpen } = renderMenu({ leaf: tableLeaf });
      expect(withoutOpen.querySelector('hr')).not.toBeNull();

      const { container: withFolder } = renderMenu({ tree: { id: 'folder-id', leaves: [hitLeaf] } });
      expect(withFolder.querySelector('hr')).toBeNull();
    });
  });

  describe('menu items for folders', () => {
    const folderTree: Tree = { id: 'folder-id', leaves: [hitLeaf, referenceLeaf] };

    it('shows only "Remove folder" for a folder (no open URL)', () => {
      renderMenu({ tree: folderTree });
      expect(screen.queryByTestId('open-item')).not.toBeInTheDocument();
      expect(screen.getByTestId('remove-item')).toBeInTheDocument();
    });

    it('labels the remove button "Remove folder" for a tree', () => {
      renderMenu({ tree: folderTree as Tree });
      expect(screen.getByTestId('remove-item')).toHaveTextContent('page.cases.sidebar.folder.remove');
    });
  });

  describe('"Open item" action', () => {
    it('calls window.open with the hit URL', () => {
      renderMenu({ leaf: hitLeaf });
      act(() => {
        fireEvent.click(screen.getByTestId('open-item'));
      });
      expect(window.open).toHaveBeenCalledWith('/hits/hit-123', '_blank', 'noopener noreferrer');
    });

    it('calls window.open with the reference URL directly', () => {
      renderMenu({ leaf: referenceLeaf });
      act(() => {
        fireEvent.click(screen.getByTestId('open-item'));
      });
      expect(window.open).toHaveBeenCalledWith('https://example.com', '_blank', 'noopener noreferrer');
    });

    it('calls window.open with the event URL', () => {
      renderMenu({ leaf: eventLeaf });
      act(() => {
        fireEvent.click(screen.getByTestId('open-item'));
      });
      expect(window.open).toHaveBeenCalledWith('/events/obs-456', '_blank', 'noopener noreferrer');
    });

    it('calls window.open with the case URL', () => {
      renderMenu({ leaf: caseLeaf });
      act(() => {
        fireEvent.click(screen.getByTestId('open-item'));
      });
      expect(window.open).toHaveBeenCalledWith('/cases/nested-case-id', '_blank', 'noopener noreferrer');
    });
  });

  describe('"Remove item" action for a leaf', () => {
    it('calls dispatchApi with the delete call for the leaf', async () => {
      renderMenu({ leaf: hitLeaf });
      act(() => {
        fireEvent.click(screen.getByTestId('remove-item'));
      });
      await waitFor(() => {
        expect(mockDel).toHaveBeenCalledWith('case-1', ['id-hit']);
      });
    });

    it('calls onUpdate with the updated case after the delete resolves', async () => {
      const onUpdate = vi.fn();
      renderMenu({ leaf: hitLeaf, onUpdate: onUpdate });
      act(() => {
        fireEvent.click(screen.getByTestId('remove-item'));
      });
      await waitFor(() => {
        expect(onUpdate).toHaveBeenCalledWith(mockCase);
      });
    });

    it('does not call the API when case_id is missing', () => {
      renderMenu({ _case: createMockCase({ case_id: undefined, title: 'No ID' }), leaf: hitLeaf });
      act(() => {
        fireEvent.click(screen.getByTestId('remove-item'));
      });
      expect(mockDel).not.toHaveBeenCalled();
    });

    it('skips items with no id', async () => {
      const noIdLeaf: Item = { type: 'hit', value: 'some-val' };
      renderMenu({ leaf: noIdLeaf });
      act(() => {
        fireEvent.click(screen.getByTestId('remove-item'));
      });
      await waitFor(() => {
        expect(mockDel).not.toHaveBeenCalled();
      });
    });
  });

  describe('"Rename item" action', () => {
    it('shows "Rename item" entry for a hit leaf', () => {
      renderMenu({ leaf: hitLeaf });
      expect(screen.getByTestId('rename-item')).toBeInTheDocument();
    });

    it('shows "Rename item" for a table leaf', () => {
      renderMenu({ leaf: tableLeaf });
      expect(screen.getByTestId('rename-item')).toBeInTheDocument();
    });

    it('does not show "Rename item" for a folder', () => {
      renderMenu({ tree: { id: 'folder-id', leaves: [hitLeaf] } });
      expect(screen.queryByTestId('rename-item')).not.toBeInTheDocument();
    });

    it('calls showModal when "Rename item" is clicked', () => {
      renderMenu({ leaf: hitLeaf });
      act(() => {
        fireEvent.click(screen.getByTestId('rename-item'));
      });
      expect(mockShowModal).toHaveBeenCalledTimes(1);
    });

    it('passes the current case and leaf to the rename modal', () => {
      const onUpdate = vi.fn();
      renderMenu({ leaf: hitLeaf, onUpdate: onUpdate });
      act(() => {
        fireEvent.click(screen.getByTestId('rename-item'));
      });
      const [modalElement] = mockShowModal.mock.calls[0];
      expect(modalElement.props._case).toBe(mockCase);
      expect(modalElement.props.leaf).toBe(hitLeaf);
    });

    it('works fine when onUpdate is not provided', () => {
      renderMenu({ leaf: hitLeaf });
      act(() => {
        fireEvent.click(screen.getByTestId('rename-item'));
      });
      expect(mockShowModal).toHaveBeenCalledTimes(1);
    });
  });

  describe('"Remove folder" action', () => {
    it('calls dispatchApi with the folder id and force flag', async () => {
      const folderTree: Tree = { id: 'folder-id', leaves: [hitLeaf, referenceLeaf] };
      renderMenu({ tree: folderTree });
      act(() => {
        fireEvent.click(screen.getByTestId('remove-item'));
      });
      await waitFor(() => {
        expect(mockDel).toHaveBeenCalledWith('case-1', ['folder-id'], true);
        expect(mockDel).toHaveBeenCalledTimes(1);
      });
    });

    it('calls dispatchApi with the folder id for nested subfolders', async () => {
      const nestedTree: Tree = {
        id: 'folder-id',
        leaves: [hitLeaf],
        folders: {
          subfolder: { id: 'subfolder-id', leaves: [referenceLeaf] }
        }
      };
      renderMenu({ tree: nestedTree });
      act(() => {
        fireEvent.click(screen.getByTestId('remove-item'));
      });
      await waitFor(() => {
        expect(mockDel).toHaveBeenCalledWith('case-1', ['folder-id'], true);
        expect(mockDel).toHaveBeenCalledTimes(1);
      });
    });

    it('calls onUpdate with the updated case after deletion', async () => {
      const onUpdate = vi.fn();
      const folderTree: Tree = { id: 'folder-id', leaves: [hitLeaf, referenceLeaf] };
      renderMenu({ tree: folderTree, onUpdate: onUpdate });
      act(() => {
        fireEvent.click(screen.getByTestId('remove-item'));
      });
      await waitFor(() => {
        expect(onUpdate).toHaveBeenCalledWith(mockCase);
      });
    });

    it('does not call the API or onUpdate for a folder without id', () => {
      const onUpdate = vi.fn();
      renderMenu({ tree: { leaves: [] } as Tree, onUpdate: onUpdate });
      act(() => {
        fireEvent.click(screen.getByTestId('remove-item'));
      });
      expect(mockDel).not.toHaveBeenCalled();
      expect(onUpdate).not.toHaveBeenCalled();
    });
  });
});
