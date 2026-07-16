/// <reference types="vitest" />
import { render, screen, waitFor } from '@testing-library/react';
import type { Case } from 'models/entities/generated/Case';
import type { Item } from 'models/entities/generated/Item';
import { setupReactRouterMock } from 'tests/mocks';
import { createMockCase } from 'tests/utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockApiGet = vi.hoisted(() => vi.fn());

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('api', () => ({
  default: {
    v2: {
      case: {
        get: mockApiGet
      }
    }
  }
}));

vi.mock('components/routes/404', () => ({
  default: () => <div id="not-found">Not Found</div>
}));

vi.mock('components/routes/hits/search/InformationPane', () => ({
  default: ({ selected }: { selected: string }) => <div id="information-pane">{selected}</div>
}));

vi.mock('./CaseDashboard', () => ({
  default: ({ caseId }: { caseId: string }) => <div id="case-dashboard">{caseId}</div>
}));

vi.mock('./MarkdownPage', () => ({
  default: ({ item }: { item: Item }) => <div id="markdown-page">{item?.value as string}</div>
}));

vi.mock('../hooks/useCase', () => ({
  default: () => ({ case: undefined, loading: false, missing: false })
}));

const { mockParams } = setupReactRouterMock();

const { default: ItemPage } = await import('./ItemPage');

describe('ItemPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default to no wildcard path unless a test sets it
    (mockParams as any)['*'] = '';
  });

  it('renders NotFoundPage when no subPath is provided', async () => {
    const _case: Case = createMockCase({ case_id: 'case-1', items: [] });

    render(<ItemPage case={_case} />);

    await waitFor(() => {
      expect(screen.getByTestId('not-found')).toBeInTheDocument();
    });
  });

  it('renders MarkdownPage when a markdown item path is resolved', async () => {
    const markdownItem: Item = {
      id: 'item-1',
      parent: null,
      type: 'markdown',
      name: 'Notes',
      value: 'Initial markdown',
      classification: 'TLP:CLEAR'
    } as any;

    const _case: Case = createMockCase({ case_id: 'case-1', items: [markdownItem] });

    (mockParams as any)['*'] = 'Notes';

    render(<ItemPage case={_case} />);

    await waitFor(() => {
      expect(screen.getByTestId('markdown-page')).toHaveTextContent('Initial markdown');
    });
  });

  it('normalizes leading/trailing slashes in subPath', async () => {
    const markdownItem: Item = {
      id: 'item-1',
      parent: null,
      type: 'markdown',
      name: 'Notes',
      value: 'Normalized markdown',
      classification: 'TLP:CLEAR'
    } as any;

    const _case: Case = createMockCase({ case_id: 'case-1', items: [markdownItem] });

    (mockParams as any)['*'] = '/Notes/';

    render(<ItemPage case={_case} />);

    await waitFor(() => {
      expect(screen.getByTestId('markdown-page')).toHaveTextContent('Normalized markdown');
    });
  });

  it('renders InformationPane for hit item paths', async () => {
    const hitItem: Item = {
      id: 'hit-1',
      parent: null,
      type: 'hit',
      name: 'Alert',
      value: 'selected-hit-id'
    } as any;

    const _case: Case = createMockCase({ case_id: 'case-1', items: [hitItem] });

    (mockParams as any)['*'] = 'Alert';

    render(<ItemPage case={_case} />);

    await waitFor(() => {
      expect(screen.getByTestId('information-pane')).toHaveTextContent('selected-hit-id');
    });
  });

  it('resolves nested case segments and renders downstream item', async () => {
    const nestedMarkdown: Item = {
      id: 'n-md-1',
      parent: null,
      type: 'markdown',
      name: 'NestedNotes',
      value: 'Nested markdown content'
    } as any;

    const childCase: Case = createMockCase({ case_id: 'child-case-123', items: [nestedMarkdown] });

    const caseLink: Item = {
      id: 'case-link-1',
      parent: null,
      type: 'case',
      name: 'Child',
      value: 'child-case-123'
    } as any;

    const _case: Case = createMockCase({ case_id: 'root-case', items: [caseLink] });

    mockDispatchApi.mockResolvedValueOnce(childCase);

    (mockParams as any)['*'] = 'Child/NestedNotes';

    render(<ItemPage case={_case} />);

    await waitFor(() => {
      expect(mockDispatchApi).toHaveBeenCalledOnce();
      expect(screen.getByTestId('markdown-page')).toHaveTextContent('Nested markdown content');
    });
  });

  it('returns NotFound when nested case has no value', async () => {
    const caseLink: Item = {
      id: 'case-link-1',
      parent: null,
      type: 'case',
      name: 'Child',
      value: undefined as any
    } as any;

    const _case: Case = createMockCase({ case_id: 'root-case', items: [caseLink] });

    (mockParams as any)['*'] = 'Child/Anything';

    render(<ItemPage case={_case} />);

    await waitFor(() => {
      expect(screen.getByTestId('not-found')).toBeInTheDocument();
    });
  });

  it('returns NotFound when nested case cannot be fetched', async () => {
    const caseLink: Item = {
      id: 'case-link-1',
      parent: null,
      type: 'case',
      name: 'Child',
      value: 'child-case-123'
    } as any;

    const _case: Case = createMockCase({ case_id: 'root-case', items: [caseLink] });

    mockDispatchApi.mockResolvedValueOnce(null);

    (mockParams as any)['*'] = 'Child/NestedNotes';

    render(<ItemPage case={_case} />);

    await waitFor(() => {
      expect(mockDispatchApi).toHaveBeenCalledOnce();
      expect(screen.getByTestId('not-found')).toBeInTheDocument();
    });
  });

  it('renders CaseDashboard when path equals nested case id', async () => {
    const caseLink: Item = {
      id: 'Child/NestedCase',
      parent: null,
      type: 'case',
      name: 'Child',
      value: 'child-case-123'
    } as any;

    const _case: Case = createMockCase({ case_id: 'root-case', items: [caseLink] });

    (mockParams as any)['*'] = 'Child/NestedCase';

    render(<ItemPage case={_case} />);

    await waitFor(() => {
      expect(mockDispatchApi).not.toHaveBeenCalled();
      expect(screen.getByTestId('case-dashboard')).toHaveTextContent('child-case-123');
    });
  });

  it('resolves hierarchical non-case parent via buildPathFromID', async () => {
    const folder: Item = {
      id: 'folder-1',
      parent: null,
      type: 'markdown',
      name: 'Folder'
    } as any;

    const doc: Item = {
      id: 'doc-1',
      parent: 'folder-1',
      type: 'markdown',
      name: 'Doc',
      value: 'Child content'
    } as any;

    const _case: Case = createMockCase({ case_id: 'case-1', items: [folder, doc] });

    (mockParams as any)['*'] = 'Folder/Doc';

    render(<ItemPage case={_case} />);

    await waitFor(() => {
      expect(screen.getByTestId('markdown-page')).toHaveTextContent('Child content');
    });
  });

  it('renders InformationPane for event item paths', async () => {
    const eventItem: Item = {
      id: 'event-1',
      parent: null,
      type: 'event',
      name: 'Incident',
      value: 'selected-event-id'
    } as any;

    const _case: Case = createMockCase({ case_id: 'case-1', items: [eventItem] });

    (mockParams as any)['*'] = 'Incident';

    render(<ItemPage case={_case} />);

    await waitFor(() => {
      expect(screen.getByTestId('information-pane')).toHaveTextContent('selected-event-id');
    });
  });

  it('falls back to JSON render for unknown item types', async () => {
    const otherItem: Item = {
      id: 'other-1',
      parent: null,
      type: 'other' as any,
      name: 'Other',
      value: 'misc'
    } as any;

    const _case: Case = createMockCase({ case_id: 'case-1', items: [otherItem] });

    (mockParams as any)['*'] = 'Other';

    const { container } = render(<ItemPage case={_case} />);

    await waitFor(() => {
      expect(container.querySelector('h1')).toBeTruthy();
      expect(container.querySelector('h1')?.textContent).toContain('other-1');
    });
  });

  it('renders NotFoundPage when no item matches the given path', async () => {
    const otherItem: Item = {
      id: 'item-2',
      parent: null,
      type: 'markdown',
      name: 'Other',
      value: 'Other content'
    } as any;

    const _case: Case = createMockCase({ case_id: 'case-1', items: [otherItem] });

    (mockParams as any)['*'] = 'UnknownPath';

    render(<ItemPage case={_case} />);

    await waitFor(() => {
      expect(screen.getByTestId('not-found')).toBeInTheDocument();
    });
  });
});
