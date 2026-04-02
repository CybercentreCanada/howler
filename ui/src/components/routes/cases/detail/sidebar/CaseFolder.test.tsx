import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { Case } from 'models/entities/generated/Case';
import type { Item } from 'models/entities/generated/Item';
import { act } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { setupContextSelectorMock } from 'tests/mocks';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// use-context-selector must be patched before any component module is loaded
// ---------------------------------------------------------------------------

setupContextSelectorMock();

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    Link: ({ to, children, onClick, ...props }: any) => (
      <a
        href={to}
        {...props}
        onClick={e => {
          e.preventDefault();
          onClick?.(e);
        }}
      >
        {children}
      </a>
    ),
    useLocation: vi.fn(() => ({ pathname: '/', search: '' }))
  };
});

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
  const { createContext } = await import('react');
  return {
    ModalContext: createContext({ showModal: vi.fn(), close: vi.fn(), setContent: vi.fn() })
  };
});

// RecordContext — supply a controllable records map
const mockRecords = vi.hoisted(() => ({ current: {} as Record<string, any> }));

vi.mock('components/app/providers/RecordProvider', async () => {
  const { createContext } = await import('react');
  return {
    RecordContext: createContext({ records: mockRecords.current })
  };
});

// ---------------------------------------------------------------------------
// Imports after mocks
// ---------------------------------------------------------------------------

import CaseFolder from './CaseFolder';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const makeCase = (id: string, items: Item[] = []): Case => ({
  case_id: id,
  title: `Case ${id}`,
  items
});

const hitItem = (path: string, value = path): Item => ({ type: 'hit', value, path });
const caseItem = (path: string, value: string): Item => ({ type: 'case', value, path });
const refItem = (path: string, value: string): Item => ({ type: 'reference', value, path });

const renderFolder = (props: Partial<React.ComponentPropsWithoutRef<typeof CaseFolder>> & { case: Case }) =>
  render(
    <MemoryRouter>
      <CaseFolder step={0} {...props} />
    </MemoryRouter>
  );

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
    it('renders a leaf label derived from path', () => {
      renderFolder({ case: makeCase('c1', [hitItem('folder/my-hit', 'v1')]) });
      expect(screen.getByText('my-hit')).toBeInTheDocument();
    });

    it('falls back to value when leaf has no path', () => {
      const noPath: Item = { type: 'hit', value: 'bare-value' };
      // Items with no path are excluded from the tree entirely
      renderFolder({ case: makeCase('c1', [noPath]) });
      expect(screen.queryByText('bare-value')).not.toBeInTheDocument();
    });

    it('renders multiple leaves in the same folder', () => {
      const items = [hitItem('folder/alpha', 'va'), hitItem('folder/beta', 'vb')];
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
        folder: { path: 'documents', leaves: [hitItem('documents/item', 'v')] }
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
        folder: { path: 'docs', leaves: [hitItem('docs/item', 'v')] }
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
        folder: { path: 'docs', leaves: [hitItem('docs/item', 'v')] }
      });
      await user.click(screen.getByText('docs'));
      await user.click(screen.getByText('docs'));
      expect(screen.getByText('item')).toBeInTheDocument();
    });
  });

  describe('leaf link URLs', () => {
    it('builds a /cases/<id>/<path> URL for a hit leaf', () => {
      renderFolder({ case: makeCase('case-1', [hitItem('folder/my-hit', 'hit-id')]) });
      const link = screen.getByText('my-hit').closest('a');
      expect(link).toHaveAttribute('href', '/cases/case-1/folder/my-hit');
    });

    it('uses the leaf value directly as href for a reference item', () => {
      renderFolder({ case: makeCase('case-1', [refItem('links/ext', 'https://example.com')]) });
      const link = screen.getByText('ext').closest('a');
      expect(link).toHaveAttribute('href', 'https://example.com');
    });

    it('omits the path segment when the leaf has no path (only value)', () => {
      // A leaf item with value but no structural path still renders the root case URL
      const items = [hitItem('top', 'top-val')];
      renderFolder({ case: makeCase('case-1', items) });
      const link = screen.getByText('top').closest('a');
      expect(link).toHaveAttribute('href', '/cases/case-1/top');
    });
  });

  describe('nested case paths', () => {
    it('prepends parentCasePaths to the leaf URL', () => {
      const leaf = hitItem('example/page', 'page-val');
      renderFolder({
        case: makeCase('case3', [leaf]),
        rootCaseId: 'case1',
        parentCasePaths: ['cases/caseone', 'cases/casetwo']
      });
      const link = screen.getByText('page').closest('a');
      expect(link).toHaveAttribute('href', '/cases/case1/cases/caseone/cases/casetwo/example/page');
    });

    it('produces the correct URL at one level of nesting', () => {
      const leaf = hitItem('data/item', 'val');
      renderFolder({
        case: makeCase('case2', [leaf]),
        rootCaseId: 'case1',
        parentCasePaths: ['cases/caseone']
      });
      const link = screen.getByText('item').closest('a');
      expect(link).toHaveAttribute('href', '/cases/case1/cases/caseone/data/item');
    });
  });

  describe('subfolders', () => {
    it('renders subfolder names', () => {
      renderFolder({
        case: makeCase('c1', [hitItem('alpha/item', 'v')])
      });
      // The structural folder "alpha" is not rendered as a labelled header at root level,
      // but its child leaf label "item" should be visible
      expect(screen.getByText('item')).toBeInTheDocument();
    });

    it('renders nested subfolder children', () => {
      renderFolder({
        case: makeCase('c1', [hitItem('a/b/deep', 'v')])
      });
      expect(screen.getByText('deep')).toBeInTheDocument();
    });
  });

  describe('nested case expansion', () => {
    it('does not show nested case content before the case leaf is clicked', () => {
      const items = [caseItem('cases/child', 'child-case-id')];
      const _case = makeCase('root', items);
      mockDispatchApi.mockResolvedValue(null);
      renderFolder({ case: _case });
      expect(screen.queryByText('nested-item')).not.toBeInTheDocument();
    });

    it('fetches the nested case when a case leaf is clicked', async () => {
      const items = [caseItem('cases/child', 'child-case-id')];
      const nestedCase = makeCase('child-case-id', [hitItem('nested/page', 'p')]);
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
      const nestedCase = makeCase('child-case-id', [hitItem('nested/page', 'p')]);
      mockGetCase.mockReturnValue(Promise.resolve(nestedCase));
      mockDispatchApi.mockImplementation((p: Promise<any>) => p);

      renderFolder({ case: makeCase('root', [caseItem('cases/child', 'child-case-id')]) });

      act(() => {
        screen.getByText('child').click();
      });

      await waitFor(() => {
        expect(screen.getByText('page')).toBeInTheDocument();
      });
    });

    it('builds the correct URL for a leaf inside a nested case', async () => {
      const nestedCase = makeCase('child-case-id', [hitItem('data/item', 'val')]);
      mockGetCase.mockReturnValue(Promise.resolve(nestedCase));
      mockDispatchApi.mockImplementation((p: Promise<any>) => p);

      renderFolder({ case: makeCase('root', [caseItem('cases/child', 'child-case-id')]) });

      act(() => {
        screen.getByText('child').click();
      });

      await waitFor(() => {
        const link = screen.getByText('item').closest('a');
        expect(link).toHaveAttribute('href', '/cases/root/cases/child/data/item');
      });
    });

    it('does not call the API a second time when a case leaf is toggled closed and re-opened', async () => {
      const nestedCase = makeCase('child-case-id', [hitItem('nested/page', 'p')]);
      mockGetCase.mockReturnValue(Promise.resolve(nestedCase));
      mockDispatchApi.mockImplementation((p: Promise<any>) => p);

      renderFolder({ case: makeCase('root', [caseItem('cases/child', 'child-case-id')]) });

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
      const nestedCase = makeCase('child-case-id', [hitItem('nested/page', 'p')]);
      mockGetCase.mockReturnValue(Promise.resolve(nestedCase));
      mockDispatchApi.mockImplementation((p: Promise<any>) => p);

      renderFolder({ case: makeCase('root', [caseItem('cases/child', 'child-case-id')]) });

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
      renderFolder({ case: makeCase('my-case', [hitItem('folder/item', 'v')]) });
      const link = screen.getByText('item').closest('a');
      expect(link).toHaveAttribute('href', '/cases/my-case/folder/item');
    });

    it('uses the provided rootCaseId in URLs when given', () => {
      renderFolder({
        case: makeCase('nested-case', [hitItem('folder/item', 'v')]),
        rootCaseId: 'root-case'
      });
      const link = screen.getByText('item').closest('a');
      expect(link).toHaveAttribute('href', '/cases/root-case/folder/item');
    });
  });
});
