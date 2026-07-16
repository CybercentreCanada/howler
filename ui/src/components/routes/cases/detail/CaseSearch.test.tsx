/// <reference types="vitest" />
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { HowlerSearchResponse } from 'api/search';
import type { FuzzySearchItem } from 'api/v2/fuzzy';
import { setupContextSelectorMock, setupLocalStorageMock } from 'tests/mocks';
import { createMockCase, createMockEvent, createMockHit } from 'tests/utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Setup common mocks
// ---------------------------------------------------------------------------

setupContextSelectorMock();
const mockLocalStorage = setupLocalStorageMock();

const mockFuzzyPost = vi.hoisted(() => vi.fn());

vi.mock('api', () => ({
  default: {
    v2: {
      fuzzy: {
        post: (...args: unknown[]) => mockFuzzyPost(...args)
      }
    }
  }
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    // Provide a parent case via outlet context for CaseSearch
    useOutletContext: () =>
      createMockCase({
        case_id: 'parent-case',
        items: [{ type: 'case', value: 'child-1' } as any, { type: 'case', value: 'child-2' } as any]
      })
  };
});

// The cards render skeletons when records aren't in RecordContext. We don't
// need full RecordProvider—verify presence via ids/text content.
vi.mock('components/elements/hit/HitCard', () => ({
  default: ({ id }: { id?: string }) => <div id={`hit-card-${id}`}>Hit {id}</div>
}));
vi.mock('components/elements/event/EventCard', () => ({
  default: ({ id }: { id?: string }) => <div id={`event-card-${id}`}>Event {id}</div>
}));
vi.mock('components/elements/case/CaseCard', () => ({
  default: ({ caseId }: { caseId?: string }) => <div id={`case-card-${caseId}`}>Case {caseId}</div>
}));

// ---------------------------------------------------------------------------
// Import after mocks
// ---------------------------------------------------------------------------
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import i18n from 'i18n';
import { useState } from 'react';
import { I18nextProvider } from 'react-i18next';
import CaseSearch from './CaseSearch';

// Helper to make a response object
const makeResponse = (
  overrides?: Partial<HowlerSearchResponse<FuzzySearchItem>>
): HowlerSearchResponse<FuzzySearchItem> => ({
  items: [],
  offset: 0,
  rows: 25,
  total: 0,
  ...overrides
});

describe('CaseSearch', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockLocalStorage.clear();
  });

  const MakeWrapper = ({ children }: { children: React.ReactNode }) => {
    const [query, setQuery] = useState('');
    const [indexes] = useState<string[]>([]);
    return (
      <I18nextProvider i18n={i18n as any}>
        <ParameterContext.Provider value={{ indexes, query, setQuery } as any}>{children}</ParameterContext.Provider>
      </I18nextProvider>
    );
  };

  it('renders SearchTotal and pagination after a successful search', async () => {
    const hit = createMockHit({ howler: { id: 'hit-1' } });
    const event = createMockEvent({ howler: { id: 'event-1' } });

    mockFuzzyPost.mockResolvedValueOnce(
      makeResponse({ items: [hit as any, event as any], total: 100, rows: 25, offset: 0 })
    );

    render(<CaseSearch />, { wrapper: MakeWrapper });

    // Trigger search by clicking the button in FuzzySearchBar
    // First, type a query into the input and click the search icon
    const user = userEvent.setup();
    const input = screen.getByTestId('fuzzy-search-input') as HTMLInputElement;
    await user.type(input, 'howler.id:*');
    await user.click(screen.getByTestId('fuzzy-search-button'));

    await waitFor(() => {
      // Total text appears
      expect(screen.getByText(/Showing 1 to 2 of 100 results/)).toBeInTheDocument();
      // Pagination navigation renders
      expect(screen.getByRole('navigation')).toBeInTheDocument();
    });
  });

  it('calls fuzzy search with default indexes when none selected', async () => {
    mockFuzzyPost.mockResolvedValueOnce(makeResponse({ items: [], total: 0 }));

    render(<CaseSearch />, { wrapper: MakeWrapper });

    const user = userEvent.setup();
    const input = screen.getByTestId('fuzzy-search-input') as HTMLInputElement;
    await user.type(input, 'test');
    await user.click(screen.getByTestId('fuzzy-search-button'));

    await waitFor(() => {
      expect(mockFuzzyPost).toHaveBeenCalledTimes(1);
      const arg = mockFuzzyPost.mock.calls[0][0] as any;
      expect(arg.query).toBe('test');
      expect(arg.rows).toBe(25);
      expect(arg.offset).toBe(0);
      expect(arg.indexes).toEqual(['case', 'hit', 'event']);
      // When indexes array is empty, CaseSearch uses defaults
      // Filters are included when case context exists; exact text is implementation detail
    });
  });

  it('renders appropriate cards for hit, event and case items', async () => {
    const hit = { ...createMockHit({ howler: { id: 'hit-123' } }), _score: 1 } as any;
    const event = { ...createMockEvent({ howler: { id: 'event-456' } }), _score: 1 } as any;
    const caseItem: FuzzySearchItem = { __index: 'case', case_id: 'case-789', _score: 1 } as any;

    mockFuzzyPost.mockResolvedValueOnce(makeResponse({ items: [hit, event, caseItem], total: 3, offset: 0 }));

    render(<CaseSearch />, { wrapper: MakeWrapper });

    const user = userEvent.setup();
    const input = screen.getByTestId('fuzzy-search-input') as HTMLInputElement;
    await user.type(input, 'anything');
    await user.click(screen.getByTestId('fuzzy-search-button'));

    await waitFor(() => {
      expect(screen.getByTestId('hit-card-hit-123')).toBeInTheDocument();
      expect(screen.getByTestId('event-card-event-456')).toBeInTheDocument();
      expect(screen.getByTestId('case-card-case-789')).toBeInTheDocument();
    });
  });

  it('updates offset via pagination and re-runs search', async () => {
    // First response with 100 total and 25 rows; clicking page 2 should set offset=25
    mockFuzzyPost
      .mockResolvedValueOnce(makeResponse({ items: [], total: 100, rows: 25, offset: 0 }))
      .mockResolvedValueOnce(makeResponse({ items: [], total: 100, rows: 25, offset: 25 }));

    render(<CaseSearch />, { wrapper: MakeWrapper });

    const user = userEvent.setup();
    const input = screen.getByTestId('fuzzy-search-input') as HTMLInputElement;
    await user.type(input, 'page');
    await user.click(screen.getByTestId('fuzzy-search-button'));

    await waitFor(() => {
      expect(screen.getByRole('navigation')).toBeInTheDocument();
    });

    await user.click(screen.getByText('2'));

    await waitFor(() => {
      // Second call should include offset 25
      const second = mockFuzzyPost.mock.calls[1][0] as any;
      expect(second.offset).toBe(25);
    });
  });

  it('shows error text when search fails', async () => {
    mockFuzzyPost.mockRejectedValueOnce(new Error('Boom'));

    render(<CaseSearch />, { wrapper: MakeWrapper });
    const user = userEvent.setup();
    const input = screen.getByTestId('fuzzy-search-input') as HTMLInputElement;
    await user.type(input, 'bad');
    await user.click(screen.getByTestId('fuzzy-search-button'));

    await waitFor(() => {
      expect(screen.getByText('Boom')).toBeInTheDocument();
    });
  });
});
