import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import omit from 'lodash-es/omit';
import { act, type PropsWithChildren } from 'react';
import { setupContextSelectorMock, setupReactRouterMock } from 'tests/mocks';
import { DEFAULT_QUERY } from 'utils/constants';

// Mock the API
const mockApiSearchHitPost = vi.fn();
const mockApiDossierGet = vi.fn();
const mockApiDossierPost = vi.fn();
const mockApiDossierPut = vi.fn();
vi.mock('api', () => ({
  default: {
    search: {
      hit: {
        post: (...args) => mockApiSearchHitPost(...args)
      }
    },
    dossier: {
      get: (...args) => mockApiDossierGet(...args),
      post: (...args) => mockApiDossierPost(...args),
      put: (...args) => mockApiDossierPut(...args)
    }
  }
}));

setupReactRouterMock();
setupContextSelectorMock();

vi.mock('components/elements/ThemedEditor', () => ({
  default: ({ value, onChange, id }) => {
    return (
      <input
        id={id || 'themed-editor'}
        value={value}
        onChange={e => {
          onChange?.((e.target as HTMLInputElement).value, true);
        }}
      />
    );
  }
}));

vi.mock('@monaco-editor/react', async () => {
  const actual = await vi.importActual('@monaco-editor/react');
  return { ...actual, useMonaco: vi.fn() };
});

// Mock iconExists
vi.mock('@iconify/react/dist/iconify.js', () => ({
  Icon: ({ ...args }) => <div {...args}>{'iconify'}</div>,
  iconExists: (icon: string) => icon?.startsWith('material-symbols:') || icon === 'test-icon'
}));

// Mock MUI components
vi.mock('@mui/material', async () => {
  const actual: any = await vi.importActual('@mui/material');

  return {
    ...actual,
    Autocomplete: ({ ...props }) => {
      return <actual.Autocomplete {...props} />;
    },
    CircularProgress: ({ ...props }) => <div role="progressbar" id="loading" {...omit(props, ['flexItem', 'sx'])} />,
    LinearProgress: ({ ...props }) => <div role="progressbar" id="loading" {...omit(props, ['flexItem', 'sx'])} />
  };
});

// Mock child components
vi.mock('commons/components/pages/PageCenter', () => ({
  default: ({ children, ...props }) => (
    <div id="page-center" {...omit(props, ['textAlign', 'maxWidth'])}>
      {children}
    </div>
  )
}));

vi.mock('../../elements/display/QueryResultText', () => ({
  default: ({ count, query }) => (
    <div id="query-result-text">
      {count} {' results for '} {query}
    </div>
  )
}));

vi.mock('../hits/search/HitQuery', () => ({
  default: ({ onChange, triggerSearch, disabled }) => {
    return (
      <div id="hit-query">
        <input
          id="query-input"
          disabled={disabled}
          onChange={e => {
            onChange?.((e.target as HTMLInputElement).value, false);
          }}
          onKeyDown={e => {
            if (e.key === 'Enter') {
              triggerSearch((e.target as HTMLInputElement).value);
            }
          }}
        />
        <button id="trigger-search" onClick={() => triggerSearch(DEFAULT_QUERY)}>
          {'search'}
        </button>
      </div>
    );
  }
}));

import ApiConfigProvider from 'components/app/providers/ApiConfigProvider';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import i18n from 'i18n';
import { I18nextProvider } from 'react-i18next';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import DossierEditor from './DossierEditor';

const mockUseParams = vi.mocked(useParams);
const mockUseSearchParams = vi.mocked(useSearchParams);
// eslint-disable-next-line react-hooks/rules-of-hooks
const mockNavigate = vi.mocked(useNavigate());

// Mock ParameterContext
const mockSetQuery = vi.fn();
let mockParameterContext = {
  setQuery: mockSetQuery
};

// Mock data
const mockDossier = {
  dossier_id: 'test-dossier-1',
  id: 'test-dossier-1',
  title: 'Test Dossier',
  type: 'global' as const,
  query: DEFAULT_QUERY,
  leads: [
    {
      label: { en: 'Lead 1', fr: 'Piste 1' },
      icon: 'material-symbols:info',
      format: 'markdown',
      content: '# Hello, World'
    }
  ],
  pivots: [
    {
      label: { en: 'Pivot 1', fr: 'Pivot 1' },
      icon: 'material-symbols:link',
      format: 'link',
      value: 'pivot.field',
      mappings: [{ key: 'key1', field: 'howler.id' }]
    }
  ]
};

const Wrapper = ({ children }: PropsWithChildren) => {
  return (
    <I18nextProvider i18n={i18n as any} defaultNS="translation">
      <ApiConfigProvider
        defaultConfig={
          {
            indexes: { hit: { 'howler.id': {} } },
            lookups: {},
            configuration: {},
            c12nDef: {},
            mapping: {}
          } as any
        }
      >
        <ParameterContext.Provider value={mockParameterContext as any}>{children}</ParameterContext.Provider>
      </ApiConfigProvider>
    </I18nextProvider>
  );
};

describe('DossierEditor', () => {
  beforeEach(() => {
    mockApiSearchHitPost.mockClear();
    mockApiDossierGet.mockClear();
    mockApiDossierPost.mockClear();
    mockApiDossierPut.mockClear();
    mockNavigate.mockClear();
    mockSetQuery.mockClear();

    // Reset mock context
    mockParameterContext.setQuery = mockSetQuery;

    // Default mock implementations
    mockApiSearchHitPost.mockResolvedValue({ total: 42, items: [] });
  });

  describe('Component initialization', () => {
    beforeEach(() => {
      mockApiDossierGet.mockClear();
    });

    it('should render with default values for new dossier', async () => {
      mockUseParams.mockReturnValueOnce({ id: null });

      render(
        <Wrapper>
          <DossierEditor />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByTestId('dossier-title')).toBeInTheDocument();
      });

      expect(screen.getByTestId('dossier-title')).toHaveValue('');
      expect(screen.getByTestId('hit-query')).toBeInTheDocument();
    });

    it('should load existing dossier when id is provided', async () => {
      mockApiDossierGet.mockResolvedValueOnce(mockDossier);
      mockUseParams.mockReturnValue({ id: 'test-dossier-1' });

      render(
        <Wrapper>
          <DossierEditor />
        </Wrapper>
      );

      await waitFor(() => {
        expect(mockApiDossierGet).toHaveBeenCalledOnce();
      });

      await waitFor(() => {
        expect(screen.getByTestId('dossier-title')).toHaveValue('Test Dossier');
      });
    });

    it('should show loading state while fetching dossier', async () => {
      let resolvePromise;
      const delayedPromise = new Promise(resolve => {
        resolvePromise = resolve;
      });
      mockApiDossierGet.mockReturnValue(delayedPromise);
      mockUseParams.mockReturnValue({ id: 'test-dossier-1' });

      const { rerender } = render(
        <Wrapper>
          <DossierEditor />
        </Wrapper>
      );

      await waitFor(() => {
        expect(mockApiDossierGet).toHaveBeenCalledOnce();
      });

      rerender(
        <Wrapper>
          <DossierEditor />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByRole('progressbar')).toBeInTheDocument();
      });

      // Resolve the promise
      resolvePromise(mockDossier);

      rerender(
        <Wrapper>
          <DossierEditor />
        </Wrapper>
      );

      await waitFor(() => {
        expect(mockApiDossierGet).toHaveBeenCalled();
        expect(screen.getByTestId('dossier-title')).toHaveValue('Test Dossier');
      });
    });

    describe('Form interactions', () => {
      it('should update title field', async () => {
        const user = userEvent.setup();

        const { rerender } = render(
          <Wrapper>
            <DossierEditor />
          </Wrapper>
        );

        const titleInput = screen.getByTestId('dossier-title');

        await user.click(titleInput);
        await user.keyboard('{Control>}a{/Control}{Backspace}');
        await user.keyboard('My New Dossier');

        rerender(
          <Wrapper>
            <DossierEditor />
          </Wrapper>
        );

        await waitFor(() => {
          expect(titleInput).toHaveValue('My New Dossier');
        });
      });

      it('should toggle between global and personal type', async () => {
        const user = userEvent.setup();

        render(
          <Wrapper>
            <DossierEditor />
          </Wrapper>
        );

        const personalButton = screen.getByRole('button', { name: /personal/i });
        const globalButton = screen.getByRole('button', { name: /global/i });

        await user.click(personalButton);

        // The toggle button should now show personal as selected
        expect(personalButton).toHaveAttribute('aria-pressed', 'true');
        expect(globalButton).toHaveAttribute('aria-pressed', 'false');

        await user.click(globalButton);

        // The toggle button should now show personal as selected
        expect(personalButton).toHaveAttribute('aria-pressed', 'false');
        expect(globalButton).toHaveAttribute('aria-pressed', 'true');
      });

      it('should trigger search when query changes', async () => {
        const user = userEvent.setup();

        render(
          <Wrapper>
            <DossierEditor />
          </Wrapper>
        );

        const queryInput = screen.getByTestId('query-input');

        await user.click(queryInput);
        await user.keyboard('{Control>}a{/Control}{Backspace}');
        await user.keyboard('test query');
        await user.keyboard('{Enter}');

        await waitFor(() => {
          expect(mockApiSearchHitPost).toHaveBeenCalledWith({
            query: 'test query',
            rows: 0
          });
        });
      });

      it('should display query result count after search', async () => {
        const user = userEvent.setup();

        render(
          <Wrapper>
            <DossierEditor />
          </Wrapper>
        );

        const queryInput = screen.getByTestId('query-input');

        await user.type(queryInput, 'test query');
        await user.keyboard('{Enter}');

        await waitFor(() => {
          expect(screen.getByTestId('query-result-text')).toBeInTheDocument();
        });
      });
    });

    describe('Tabs', () => {
      it('should render leads and pivots tabs', async () => {
        render(
          <Wrapper>
            <DossierEditor />
          </Wrapper>
        );

        await waitFor(() => {
          expect(screen.getByRole('tab', { name: /leads/i })).toBeInTheDocument();
          expect(screen.getByRole('tab', { name: /pivots/i })).toBeInTheDocument();
        });
      });

      it('should show LeadForm by default', async () => {
        render(
          <Wrapper>
            <DossierEditor />
          </Wrapper>
        );

        await waitFor(() => {
          expect(screen.getByTestId('lead-form')).toBeInTheDocument();
        });
      });

      it('should switch to PivotForm when pivots tab is clicked', async () => {
        const user = userEvent.setup();

        render(
          <Wrapper>
            <DossierEditor />
          </Wrapper>
        );

        const pivotsTab = screen.getByRole('tab', { name: /pivots/i });
        await user.click(pivotsTab);

        await waitFor(() => {
          expect(screen.getByTestId('pivot-form')).toBeInTheDocument();
        });
      });
    });

    describe('Validation', () => {
      it('should disable save button when title is missing', async () => {
        render(
          <Wrapper>
            <DossierEditor />
          </Wrapper>
        );

        await waitFor(() => {
          const saveButton = screen.getByRole('button', { name: /save/i });
          expect(saveButton).toBeDisabled();
        });
      });

      it('should disable save button when no leads or pivots exist', async () => {
        mockUseParams.mockReturnValue({ id: null });

        const user = userEvent.setup();

        render(
          <Wrapper>
            <DossierEditor />
          </Wrapper>
        );

        const titleInput = screen.getByTestId('dossier-title');
        await user.type(titleInput, 'Test Title');

        const queryInput = screen.getByTestId('query-input');
        user.click(queryInput);
        await user.keyboard('test query');
        await user.keyboard('{Enter}');

        await waitFor(() => {
          expect(screen.getByTestId('query-result-text')).toBeInTheDocument();
        });

        const saveButton = screen.getByRole('button', { name: /save/i });
        expect(saveButton).toBeDisabled();
      });

      it('should enable save button when all required fields are filled', async () => {
        mockUseParams.mockReturnValue({ id: null });
        const searchParams = new URLSearchParams('tab=leads');
        const mockSetSearchParams = vi.fn();
        mockUseSearchParams.mockReturnValue([searchParams, mockSetSearchParams]);

        const user = userEvent.setup();

        render(
          <Wrapper>
            <DossierEditor />
          </Wrapper>
        );

        await act(async () => {
          // Fill title
          const titleInput = screen.getByTestId('dossier-title');
          await user.type(titleInput, 'Test Title');

          // Add query and trigger search
          const queryInput = screen.getByTestId('query-input');
          await user.click(queryInput);
          await user.keyboard('test query');
          await user.keyboard('{Enter}');
        });

        await waitFor(() => {
          expect(screen.getByTestId('query-result-text')).toBeInTheDocument();
          expect(screen.getByTestId('create-lead-alert')).toBeInTheDocument();
        });

        // Add a lead
        await user.click(screen.getByTestId('add-lead'));

        await waitFor(() => {
          expect(screen.getByTestId('lead-format')).toBeInTheDocument();
        });

        await user.click(screen.getByTestId('lead-format'));
        await user.keyboard('markdown');
        await user.keyboard('[ArrowDown]');
        await user.keyboard('{Enter}');

        await user.click(screen.getByTestId('lead-markdown'));
        await user.keyboard('hello world');

        await waitFor(() => {
          const saveButton = screen.getByRole('button', { name: /save/i });
          expect(saveButton).not.toBeDisabled();
        });
      });
    });

    describe('Dirty state tracking', () => {
      it('should mark form as dirty when changes are made', async () => {
        const user = userEvent.setup();

        mockUseParams.mockReturnValue({ id: 'test-dossier-1' });
        mockApiDossierGet.mockResolvedValueOnce(mockDossier);
        mockApiSearchHitPost.mockResolvedValueOnce({ total: -1, items: [] });

        render(
          <Wrapper>
            <DossierEditor />
          </Wrapper>
        );

        await waitFor(() => {
          expect(screen.getByTestId('dossier-title')).toHaveValue('Test Dossier');
        });

        const saveButton = screen.getByRole('button', { name: /save/i });
        expect(saveButton).toBeDisabled();

        // Make a change
        const queryInput = screen.getByTestId('query-input');
        await user.click(queryInput);
        await user.keyboard('test query');
        await user.keyboard('{Enter}');

        await waitFor(() => {
          expect(saveButton).not.toBeDisabled();
        });
      });

      it('should not mark form as dirty when no changes are made', async () => {
        mockUseParams.mockReturnValue({ id: 'test-dossier-1' });
        mockApiDossierGet.mockResolvedValueOnce(mockDossier);
        mockApiSearchHitPost.mockResolvedValueOnce({ total: 10, items: [] });

        render(
          <Wrapper>
            <DossierEditor />
          </Wrapper>
        );

        await waitFor(() => {
          expect(screen.getByTestId('dossier-title')).toHaveValue('Test Dossier');
        });

        const saveButton = screen.getByRole('button', { name: /save/i });
        expect(saveButton).toBeDisabled();
      });
    });

    describe('URL parameter synchronization', () => {
      it('should initialize tab from URL search params', async () => {
        const searchParams = new URLSearchParams('tab=pivots');
        const mockSetSearchParams = vi.fn();
        mockUseSearchParams.mockReturnValue([searchParams, mockSetSearchParams]);
        mockUseParams.mockReturnValue({ id: null });

        render(
          <Wrapper>
            <DossierEditor />
          </Wrapper>
        );

        await waitFor(() => {
          const pivotsTab = screen.getByRole('tab', { name: /pivots/i });
          expect(pivotsTab).toHaveAttribute('aria-selected', 'true');
        });
      });

      it('should default to leads tab when no tab param in URL', async () => {
        const searchParams = new URLSearchParams();
        const mockSetSearchParams = vi.fn();
        mockUseSearchParams.mockReturnValue([searchParams, mockSetSearchParams]);
        mockUseParams.mockReturnValue({ id: null });

        render(
          <Wrapper>
            <DossierEditor />
          </Wrapper>
        );

        await waitFor(() => {
          const leadsTab = screen.getByRole('tab', { name: /leads/i });
          expect(leadsTab).toHaveAttribute('aria-selected', 'true');
        });
      });

      it('should update URL params when tab is changed', async () => {
        const user = userEvent.setup();
        const searchParams = new URLSearchParams();
        const mockSetSearchParams = vi.fn();
        mockUseSearchParams.mockReturnValue([searchParams, mockSetSearchParams]);
        mockUseParams.mockReturnValue({ id: null });

        render(
          <Wrapper>
            <DossierEditor />
          </Wrapper>
        );

        await waitFor(() => {
          expect(screen.getByRole('tab', { name: /pivots/i })).toBeInTheDocument();
        });

        const pivotsTab = screen.getByRole('tab', { name: /pivots/i });
        await user.click(pivotsTab);

        await waitFor(() => {
          expect(mockSetSearchParams).toHaveBeenCalled();
          const callArgs = mockSetSearchParams.mock.calls[mockSetSearchParams.mock.calls.length - 1];
          const updatedParams = callArgs[0];
          expect(updatedParams.get('tab')).toBe('pivots');
        });
      });

      it('should update search params with replace option', async () => {
        const user = userEvent.setup();
        const searchParams = new URLSearchParams();
        const mockSetSearchParams = vi.fn();
        mockUseSearchParams.mockReturnValue([searchParams, mockSetSearchParams]);
        mockUseParams.mockReturnValue({ id: null });

        render(
          <Wrapper>
            <DossierEditor />
          </Wrapper>
        );

        await waitFor(() => {
          expect(screen.getByRole('tab', { name: /pivots/i })).toBeInTheDocument();
        });

        const pivotsTab = screen.getByRole('tab', { name: /pivots/i });
        await user.click(pivotsTab);

        await waitFor(() => {
          expect(mockSetSearchParams).toHaveBeenCalled();
          const callArgs = mockSetSearchParams.mock.calls[mockSetSearchParams.mock.calls.length - 1];
          const options = callArgs[1];
          expect(options).toEqual({ replace: true });
        });
      });

      it('should set tab param when switching from leads to pivots', async () => {
        const user = userEvent.setup();
        const searchParams = new URLSearchParams('tab=leads');
        const mockSetSearchParams = vi.fn();
        mockUseSearchParams.mockReturnValue([searchParams, mockSetSearchParams]);
        mockUseParams.mockReturnValue({ id: null });

        render(
          <Wrapper>
            <DossierEditor />
          </Wrapper>
        );

        await waitFor(() => {
          expect(screen.getByRole('tab', { name: /leads/i })).toHaveAttribute('aria-selected', 'true');
        });

        const pivotsTab = screen.getByRole('tab', { name: /pivots/i });
        await user.click(pivotsTab);

        await waitFor(() => {
          expect(mockSetSearchParams).toHaveBeenCalled();
          const callArgs = mockSetSearchParams.mock.calls[mockSetSearchParams.mock.calls.length - 1];
          const updatedParams = callArgs[0];
          expect(updatedParams.get('tab')).toBe('pivots');
        });
      });

      it('should set tab param when switching from pivots to leads', async () => {
        const user = userEvent.setup();
        const searchParams = new URLSearchParams('tab=pivots');
        const mockSetSearchParams = vi.fn();
        mockUseSearchParams.mockReturnValue([searchParams, mockSetSearchParams]);
        mockUseParams.mockReturnValue({ id: null });

        render(
          <Wrapper>
            <DossierEditor />
          </Wrapper>
        );

        await waitFor(() => {
          expect(screen.getByRole('tab', { name: /pivots/i })).toHaveAttribute('aria-selected', 'true');
        });

        const leadsTab = screen.getByRole('tab', { name: /leads/i });
        await user.click(leadsTab);

        await waitFor(() => {
          expect(mockSetSearchParams).toHaveBeenCalled();
          const callArgs = mockSetSearchParams.mock.calls[mockSetSearchParams.mock.calls.length - 1];
          const updatedParams = callArgs[0];
          expect(updatedParams.get('tab')).toBe('leads');
        });
      });

      it('should preserve existing URL params when changing tabs', async () => {
        const user = userEvent.setup();
        const searchParams = new URLSearchParams('tab=leads&other=value');
        const mockSetSearchParams = vi.fn();
        mockUseSearchParams.mockReturnValue([searchParams, mockSetSearchParams]);
        mockUseParams.mockReturnValue({ id: null });

        render(
          <Wrapper>
            <DossierEditor />
          </Wrapper>
        );

        await waitFor(() => {
          expect(screen.getByRole('tab', { name: /pivots/i })).toBeInTheDocument();
        });

        const pivotsTab = screen.getByRole('tab', { name: /pivots/i });
        await user.click(pivotsTab);

        await waitFor(() => {
          expect(mockSetSearchParams).toHaveBeenCalled();
          const callArgs = mockSetSearchParams.mock.calls[mockSetSearchParams.mock.calls.length - 1];
          const updatedParams = callArgs[0];
          expect(updatedParams.get('tab')).toBe('pivots');
          expect(updatedParams.get('other')).toBe('value');
        });
      });
    });
  });
});
