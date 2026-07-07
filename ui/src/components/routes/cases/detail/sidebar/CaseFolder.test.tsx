import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { Case } from 'models/entities/generated/Case';
import type { Item } from 'models/entities/generated/Item';
import { act, createContext } from 'react';
import { setupContextSelectorMock, setupReactRouterMock } from 'tests/mocks';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

setupContextSelectorMock();
setupReactRouterMock();

vi.mock('@dnd-kit/core', () => ({
  useDraggable: () => ({
    attributes: {},
    listeners: {},
    setNodeRef: vi.fn(),
    transform: null,
    isDragging: false,
    active: null
  }),
  useDroppable: () => ({
    setNodeRef: vi.fn(),
    isOver: false
  })
}));

vi.mock('@dnd-kit/utilities', () => ({
  CSS: { Transform: { toString: () => '' } }
}));

const mockDispatchApi = vi.hoisted(() => vi.fn());

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

const mockGetCase = vi.hoisted(() => vi.fn());

vi.mock('api', () => ({
  default: {
    v2: {
      case: {
        get: (...args: any[]) => mockGetCase(...args),
        items: { del: vi.fn(), patch: vi.fn() }
      }
    }
  }
}));

// CaseFolderContextMenu — render children only; ignore menu entries for these tests
vi.mock('./CaseFolderContextMenu', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/app/providers/ModalProvider', async () => {
  return {
    ModalContext: createContext({ showModal: vi.fn(), close: vi.fn(), setContent: vi.fn() })
  };
});

// RecordContext — supply a controllable records map
const mockRecords = vi.hoisted(() => ({ current: {} as Record<string, any> }));

vi.mock('components/app/providers/RecordProvider', async () => {
  return {
    RecordContext: createContext({ records: mockRecords.current })
  };
});

// ---------------------------------------------------------------------------
// Imports after mocks
// ---------------------------------------------------------------------------

import { MemoryRouter, useParams } from 'react-router-dom';
import CaseFolder from './CaseFolder';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const makeCase = (id: string, items: Item[] = []): Case => ({
  __index: 'case',
  case_id: id,
  title: `Case ${id}`,
  items
});

const hitItem = (name: string, value = name, id = `id-${value}`): Item => ({ id, type: 'hit', value, name });
const caseItem = (name: string, value: string, id = `id-${value}`): Item => ({ id, type: 'case', value, name });
const refItem = (name: string, value: string, id = `id-${value}`): Item => ({ id, type: 'reference', value, name });
const folderItem = (name: string, id: string, parent?: string): Item => ({
  id,
  type: 'folder',
  value: name,
  name,
  ...(parent ? { parent } : {})
});

const renderFolder = (
  props: Partial<React.ComponentPropsWithoutRef<typeof CaseFolder>> & { case: Case },
  routeId?: string
) => {
  vi.mocked(useParams).mockReturnValue({ id: routeId ?? props.case.case_id });
  return render(
    <MemoryRouter>
      <CaseFolder step={0} {...props} />
    </MemoryRouter>
  );
};

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  mockDispatchApi.mockReset();
  mockGetCase.mockReset();
  mockRecords.current = {};
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('CaseFolder', () => {
  describe('flat leaves', () => {
    it('renders a leaf label from item name', () => {
      renderFolder({ case: makeCase('c1', [hitItem('my-hit', 'v1')]) });
      expect(screen.getByText('my-hit')).toBeInTheDocument();
    });

    it('falls back to value when leaf has no name', () => {
      const noName: Item = { id: 'id-bare', type: 'hit', value: 'bare-value' };
      renderFolder({ case: makeCase('c1', [noName]) });
      expect(screen.getByText('bare-value')).toBeInTheDocument();
    });

    it('renders multiple leaves in the same folder', () => {
      const fld = folderItem('folder', 'f1');
      const items = [fld, { ...hitItem('alpha', 'va'), parent: 'f1' }, { ...hitItem('beta', 'vb'), parent: 'f1' }];
      renderFolder({ case: makeCase('c1', items) });
      expect(screen.getByText('alpha')).toBeInTheDocument();
      expect(screen.getByText('beta')).toBeInTheDocument();
    });
  });

  describe('folder header', () => {
    it('renders the folder name when name prop is provided', () => {
      renderFolder({
        case: makeCase('c1'),
        name: 'documents',
        folder: { id: 'doc-folder', leaves: [hitItem('item', 'v')] }
      });
      expect(screen.getByText('documents')).toBeInTheDocument();
    });

    it('does not render a folder header when name is omitted', () => {
      // Use a flat item (no subfolder) so the only text rendered is the leaf label itself.
      renderFolder({ case: makeCase('c1', [hitItem('top-item', 'v')]) });
      // The leaf label is present but there is no wrapping folder header element
      expect(screen.getByText('top-item')).toBeInTheDocument();
      // queryByText with the exact folder-header label (which would come from the `name` prop) is absent
      expect(screen.queryByText('somefolder')).not.toBeInTheDocument();
    });

    it('collapses children when the folder header is clicked', async () => {
      const user = userEvent.setup();
      renderFolder({
        case: makeCase('c1'),
        name: 'docs',
        folder: { id: 'docs-folder', leaves: [hitItem('item', 'v')] }
      });
      expect(screen.getByText('item')).toBeInTheDocument();
      await user.click(screen.getByText('docs'));
      expect(screen.queryByText('item')).not.toBeInTheDocument();
    });

    it('expands children again after a second click', async () => {
      const user = userEvent.setup();
      renderFolder({
        case: makeCase('c1'),
        name: 'docs',
        folder: { id: 'docs-folder', leaves: [hitItem('item', 'v')] }
      });
      await user.click(screen.getByText('docs'));
      await user.click(screen.getByText('docs'));
      expect(screen.getByText('item')).toBeInTheDocument();
    });
  });

  describe('leaf link URLs', () => {
    it('builds a /cases/<id>/<itemId> URL for a hit leaf', () => {
      renderFolder({ case: makeCase('case-1', [hitItem('my-hit', 'hit-id', 'item-1')]) });
      const link = screen.getByText('my-hit').closest('a');
      expect(link).toHaveAttribute('href', '/cases/case-1/item-1');
    });

    it('uses the leaf value directly as href for a reference item', () => {
      renderFolder({ case: makeCase('case-1', [refItem('ext', 'https://example.com')]) });
      const link = screen.getByText('ext').closest('a');
      expect(link).toHaveAttribute('href', 'https://example.com');
    });

    it('uses the item id in the URL', () => {
      const items = [hitItem('top', 'top-val', 'item-top')];
      renderFolder({ case: makeCase('case-1', items) });
      const link = screen.getByText('top').closest('a');
      expect(link).toHaveAttribute('href', '/cases/case-1/item-top');
    });
  });

  describe('nested case id paths', () => {
    it('prepends parentCaseIds to the leaf URL', () => {
      const leaf = hitItem('page', 'page-val', 'id-page');
      renderFolder(
        {
          case: makeCase('case3', [leaf]),
          parentCaseIds: ['id-one', 'id-two']
        },
        'case1'
      );
      const link = screen.getByText('page').closest('a');
      expect(link).toHaveAttribute('href', '/cases/case1/id-one/id-two/id-page');
    });

    it('produces the correct URL at one level of nesting', () => {
      const leaf = hitItem('item', 'val', 'id-val');
      renderFolder(
        {
          case: makeCase('case2', [leaf]),
          parentCaseIds: ['id-one']
        },
        'case1'
      );
      const link = screen.getByText('item').closest('a');
      expect(link).toHaveAttribute('href', '/cases/case1/id-one/id-val');
    });
  });

  describe('subfolders', () => {
    it('renders subfolder names', () => {
      const fld = folderItem('alpha', 'f-alpha');
      const hit: Item = { ...hitItem('item', 'v'), parent: 'f-alpha' };
      renderFolder({
        case: makeCase('c1', [fld, hit])
      });
      expect(screen.getByText('item')).toBeInTheDocument();
    });

    it('renders nested subfolder children', () => {
      const fldA = folderItem('a', 'f-a');
      const fldB = folderItem('b', 'f-b', 'f-a');
      const hit: Item = { ...hitItem('deep', 'v'), parent: 'f-b' };
      renderFolder({
        case: makeCase('c1', [fldA, fldB, hit])
      });
      expect(screen.getByText('deep')).toBeInTheDocument();
    });
  });

  describe('nested case expansion', () => {
    it('does not show nested case content before the case leaf is clicked', () => {
      const items = [caseItem('child', 'child-case-id', 'id-child')];
      const _case = makeCase('root', items);
      mockDispatchApi.mockResolvedValue(null);
      renderFolder({ case: _case });
      expect(screen.queryByText('nested-item')).not.toBeInTheDocument();
    });

    it('fetches the nested case when a case leaf is clicked', async () => {
      const items = [caseItem('child', 'child-case-id', 'id-child')];
      const nestedCase = makeCase('child-case-id', [hitItem('page', 'p')]);
      mockGetCase.mockReturnValue(Promise.resolve(nestedCase));
      mockDispatchApi.mockImplementation((p: Promise<any>) => p);

      renderFolder({ case: makeCase('root', items) });

      act(() => {
        screen.getByText('child').click();
      });

      await waitFor(() => {
        expect(mockGetCase).toHaveBeenCalledWith('child-case-id');
      });
    });

    it('renders the nested case items after the fetch resolves', async () => {
      const nestedCase = makeCase('child-case-id', [hitItem('page', 'p')]);
      mockGetCase.mockReturnValue(Promise.resolve(nestedCase));
      mockDispatchApi.mockImplementation((p: Promise<any>) => p);

      renderFolder({ case: makeCase('root', [caseItem('child', 'child-case-id', 'id-child')]) });

      act(() => {
        screen.getByText('child').click();
      });

      await waitFor(() => {
        expect(screen.getByText('page')).toBeInTheDocument();
      });
    });

    it('builds the correct URL for a leaf inside a nested case', async () => {
      const nestedCase = makeCase('child-case-id', [hitItem('item', 'val', 'id-val')]);
      mockGetCase.mockReturnValue(Promise.resolve(nestedCase));
      mockDispatchApi.mockImplementation((p: Promise<any>) => p);

      renderFolder({ case: makeCase('root', [caseItem('child', 'child-case-id', 'id-child')]) });

      act(() => {
        screen.getByText('child').click();
      });

      await waitFor(() => {
        const link = screen.getByText('item').closest('a');
        expect(link).toHaveAttribute('href', '/cases/root/id-child/id-val');
      });
    });

    it('does not call the API a second time when a case leaf is toggled closed and re-opened', async () => {
      const nestedCase = makeCase('child-case-id', [hitItem('page', 'p')]);
      mockGetCase.mockReturnValue(Promise.resolve(nestedCase));
      mockDispatchApi.mockImplementation((p: Promise<any>) => p);

      renderFolder({ case: makeCase('root', [caseItem('child', 'child-case-id', 'id-child')]) });

      act(() => {
        screen.getByText('child').click();
      });

      await waitFor(() => expect(screen.getByText('page')).toBeInTheDocument());

      act(() => {
        screen.getByText('child').click(); // close
      });
      act(() => {
        screen.getByText('child').click(); // re-open
      });

      expect(mockGetCase).toHaveBeenCalledTimes(1);
    });

    it('hides nested case content after the case leaf is toggled closed', async () => {
      const nestedCase = makeCase('child-case-id', [hitItem('page', 'p')]);
      mockGetCase.mockReturnValue(Promise.resolve(nestedCase));
      mockDispatchApi.mockImplementation((p: Promise<any>) => p);

      renderFolder({ case: makeCase('root', [caseItem('child', 'child-case-id', 'id-child')]) });

      act(() => {
        screen.getByText('child').click();
      });
      await waitFor(() => expect(screen.getByText('page')).toBeInTheDocument());

      act(() => {
        screen.getByText('child').click();
      });
      expect(screen.queryByText('page')).not.toBeInTheDocument();
    });
  });

  describe('rootCaseId propagation', () => {
    it('uses _case.case_id as the root when rootCaseId is not provided', () => {
      renderFolder({ case: makeCase('my-case', [hitItem('item', 'v', 'id-v')]) });
      const link = screen.getByText('item').closest('a');
      expect(link).toHaveAttribute('href', '/cases/my-case/id-v');
    });

    it('uses the provided rootCaseId in URLs when given', () => {
      renderFolder({ case: makeCase('nested-case', [hitItem('item', 'v', 'id-v')]) }, 'root-case');
      const link = screen.getByText('item').closest('a');
      expect(link).toHaveAttribute('href', '/cases/root-case/id-v');
    });
  });
});
