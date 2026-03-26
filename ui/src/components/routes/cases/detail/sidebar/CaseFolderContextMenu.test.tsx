import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { Case } from 'models/entities/generated/Case';
import type { Item } from 'models/entities/generated/Item';
import { act } from 'react';
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

vi.mock('api', () => ({
  default: {
    v2: {
      case: {
        items: {
          del: (...args: any[]) => mockDel(...args)
        }
      }
    }
  }
}));

// ---------------------------------------------------------------------------
// Imports (after mocks so that module registry picks up the stubs)
// ---------------------------------------------------------------------------

import CaseFolderContextMenu, { collectAllLeaves, getOpenUrl } from './CaseFolderContextMenu';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockCase: Case = { case_id: 'case-1', title: 'Test Case', items: [] };

const hitLeaf: Item = { type: 'hit', value: 'hit-123', path: 'folder/hit-item' };
const referenceLeaf: Item = { type: 'reference', value: 'https://example.com', path: 'folder/ref-item' };
const observableLeaf: Item = { type: 'observable', value: 'obs-456', path: 'folder/obs-item' };
const caseLeaf: Item = { type: 'case', value: 'nested-case-id', path: 'folder/case-item' };
const tableLeaf: Item = { type: 'table', value: 'table-789', path: 'folder/table-item' };
const leadLeaf: Item = { type: 'lead', value: 'lead-999', path: 'folder/lead-item' };

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
  mockDispatchApi.mockClear();
  mockDispatchApi.mockImplementation((p: Promise<any>) => p);
  mockDel.mockResolvedValue(mockCase);
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
      subfolder: { leaves: [referenceLeaf] } as Tree
    };
    expect(collectAllLeaves(tree)).toEqual([hitLeaf, referenceLeaf]);
  });

  it('returns leaves from deeply nested subfolders', () => {
    const tree: Tree = {
      leaves: [],
      level1: {
        leaves: [hitLeaf],
        level2: { leaves: [referenceLeaf] } as Tree
      } as Tree
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

  it('returns /observables/<id> for an observable item', () => {
    expect(getOpenUrl(observableLeaf)).toBe('/observables/obs-456');
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

    it('shows "Open item" and "Remove item" for an observable leaf', () => {
      renderMenu({ leaf: observableLeaf });
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

    it('shows a divider only when "Open item" is also present', () => {
      const { container: withOpen } = renderMenu({ leaf: hitLeaf });
      expect(withOpen.querySelector('hr')).not.toBeNull();

      const { container: withoutOpen } = renderMenu({ leaf: tableLeaf });
      expect(withoutOpen.querySelector('hr')).toBeNull();
    });
  });

  describe('menu items for folders', () => {
    const folderTree: Tree = { leaves: [hitLeaf, referenceLeaf] };

    it('shows only "Remove folder" for a folder (no open URL)', () => {
      renderMenu({ tree: folderTree });
      expect(screen.queryByTestId('open-item')).not.toBeInTheDocument();
      expect(screen.getByTestId('remove-item')).toBeInTheDocument();
    });

    it('labels the remove button "Remove folder" for a tree', () => {
      renderMenu({ tree: folderTree });
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

    it('calls window.open with the observable URL', () => {
      renderMenu({ leaf: observableLeaf });
      act(() => {
        fireEvent.click(screen.getByTestId('open-item'));
      });
      expect(window.open).toHaveBeenCalledWith('/observables/obs-456', '_blank', 'noopener noreferrer');
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
        expect(mockDel).toHaveBeenCalledWith('case-1', ['hit-123']);
      });
    });

    it('calls onRemoved with the updated case after the delete resolves', async () => {
      const onRemoved = vi.fn();
      renderMenu({ leaf: hitLeaf, onRemoved });
      act(() => {
        fireEvent.click(screen.getByTestId('remove-item'));
      });
      await waitFor(() => {
        expect(onRemoved).toHaveBeenCalledWith(mockCase);
      });
    });

    it('does not call the API when case_id is missing', () => {
      renderMenu({ _case: { title: 'No ID' }, leaf: hitLeaf });
      act(() => {
        fireEvent.click(screen.getByTestId('remove-item'));
      });
      expect(mockDel).not.toHaveBeenCalled();
    });

    it('skips items with no value', async () => {
      const noValueLeaf: Item = { type: 'hit', path: 'folder/no-value' };
      renderMenu({ leaf: noValueLeaf });
      act(() => {
        fireEvent.click(screen.getByTestId('remove-item'));
      });
      await waitFor(() => {
        expect(mockDel).not.toHaveBeenCalled();
      });
    });
  });

  describe('"Remove folder" action', () => {
    it('calls dispatchApi with all leaf values in a single batch call', async () => {
      const folderTree: Tree = { leaves: [hitLeaf, referenceLeaf] };
      renderMenu({ tree: folderTree });
      act(() => {
        fireEvent.click(screen.getByTestId('remove-item'));
      });
      await waitFor(() => {
        expect(mockDel).toHaveBeenCalledWith('case-1', ['hit-123', 'https://example.com']);
        expect(mockDel).toHaveBeenCalledTimes(1);
      });
    });

    it('calls dispatchApi with leaves from nested subfolders in a single batch call', async () => {
      const nestedTree: Tree = {
        leaves: [hitLeaf],
        subfolder: { leaves: [referenceLeaf] } as Tree
      };
      renderMenu({ tree: nestedTree });
      act(() => {
        fireEvent.click(screen.getByTestId('remove-item'));
      });
      await waitFor(() => {
        expect(mockDel).toHaveBeenCalledWith('case-1', expect.arrayContaining(['hit-123', 'https://example.com']));
        expect(mockDel).toHaveBeenCalledTimes(1);
      });
    });

    it('calls onRemoved with the updated case after deletion', async () => {
      const onRemoved = vi.fn();
      const folderTree: Tree = { leaves: [hitLeaf, referenceLeaf] };
      renderMenu({ tree: folderTree, onRemoved });
      act(() => {
        fireEvent.click(screen.getByTestId('remove-item'));
      });
      await waitFor(() => {
        expect(onRemoved).toHaveBeenCalledWith(mockCase);
      });
    });

    it('does not call the API or onRemoved for an empty folder', () => {
      const onRemoved = vi.fn();
      renderMenu({ tree: { leaves: [] }, onRemoved });
      act(() => {
        fireEvent.click(screen.getByTestId('remove-item'));
      });
      expect(mockDel).not.toHaveBeenCalled();
      expect(onRemoved).not.toHaveBeenCalled();
    });
  });
});
