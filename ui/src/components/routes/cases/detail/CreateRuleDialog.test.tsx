import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const mockDispatchApi = vi.hoisted(() => vi.fn());

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key, i18n: { language: 'en' } })
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('api', () => ({
  default: {
    search: {
      hit: {
        post: vi.fn()
      }
    }
  }
}));

vi.mock('components/routes/advanced/QueryEditor', () => ({
  default: ({ query, setQuery, id }: { query: string; setQuery: (q: string) => void; id?: string }) => (
    <textarea id={id ?? 'query-editor'} value={query} onChange={e => setQuery(e.target.value)} />
  )
}));

vi.mock('components/elements/display/QueryResultText', () => ({
  default: ({ count, query }: { count: number; query: string }) => (
    <div id="query-result-text">
      {count} results for {query}
    </div>
  )
}));

vi.mock('@monaco-editor/react', () => ({
  useMonaco: () => null
}));

vi.mock('@mui/x-date-pickers', () => ({
  LocalizationProvider: ({ children }: any) => <>{children}</>
}));

vi.mock('@mui/x-date-pickers/AdapterDayjs', () => ({
  AdapterDayjs: class {}
}));

vi.mock('@mui/x-date-pickers/DateTimePicker', () => ({
  DateTimePicker: ({ label, disabled }: { label: string; disabled?: boolean }) => (
    <input id="rule-timeframe-input" aria-label={label} disabled={disabled} readOnly />
  )
}));

import api from 'api';
import CreateRuleDialog from './CreateRuleDialog';

describe('CreateRuleDialog', () => {
  const defaultProps = {
    open: true,
    onClose: vi.fn(),
    onSubmit: vi.fn().mockResolvedValue(undefined)
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders nothing when closed', () => {
    render(<CreateRuleDialog {...defaultProps} open={false} />);

    expect(screen.queryByTestId('create-rule-dialog')).not.toBeInTheDocument();
  });

  it('renders dialog fields when open', () => {
    render(<CreateRuleDialog {...defaultProps} />);

    expect(screen.getByTestId('create-rule-dialog')).toBeInTheDocument();
    expect(screen.getByTestId('rule-query-editor')).toBeInTheDocument();
    expect(screen.getByTestId('rule-destination-input')).toBeInTheDocument();
    expect(screen.getByTestId('rule-timeframe-input')).toBeInTheDocument();
    expect(screen.getByTestId('rule-no-expiry-checkbox')).toBeInTheDocument();
    expect(screen.getByTestId('rule-index-hit')).toBeInTheDocument();
    expect(screen.getByTestId('rule-index-observable')).toBeInTheDocument();
  });

  it('disables submit when query is empty', () => {
    render(<CreateRuleDialog {...defaultProps} />);

    expect(screen.getByTestId('rule-submit-button')).toBeDisabled();
  });

  it('disables submit when destination is empty', async () => {
    const user = userEvent.setup();

    render(<CreateRuleDialog {...defaultProps} />);

    await act(async () => {
      await user.type(screen.getByTestId('rule-query-editor'), 'event.kind:alert');
    });

    expect(screen.getByTestId('rule-submit-button')).toBeDisabled();
  });

  it('enables submit when query, destination are filled and search has been run', async () => {
    const user = userEvent.setup();
    mockDispatchApi.mockResolvedValueOnce({ items: [], total: 5, offset: 0, rows: 0 });
    (api.search.hit.post as ReturnType<typeof vi.fn>).mockReturnValue('search-request');

    render(<CreateRuleDialog {...defaultProps} />);

    await act(async () => {
      await user.type(screen.getByTestId('rule-query-editor'), 'event.kind:alert');
    });

    await act(async () => {
      await user.click(screen.getByTestId('rule-search-button'));
    });

    await act(async () => {
      await user.type(screen.getByTestId('rule-destination-input'), 'alerts/incoming');
    });

    await waitFor(() => {
      expect(screen.getByTestId('rule-submit-button')).not.toBeDisabled();
    });
  });

  it('calls onSubmit with rule data when submitted', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    mockDispatchApi.mockResolvedValueOnce({ items: [], total: 1, offset: 0, rows: 0 });
    (api.search.hit.post as ReturnType<typeof vi.fn>).mockReturnValue('search-request');

    render(<CreateRuleDialog {...defaultProps} onSubmit={onSubmit} />);

    await act(async () => {
      await user.type(screen.getByTestId('rule-query-editor'), 'event.kind:alert');
    });

    await act(async () => {
      await user.click(screen.getByTestId('rule-search-button'));
    });

    await act(async () => {
      await user.type(screen.getByTestId('rule-destination-input'), 'alerts/incoming');
    });

    await act(async () => {
      await user.click(screen.getByTestId('rule-submit-button'));
    });

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          query: 'event.kind:alert',
          destination: 'alerts/incoming',
          indexes: ['hit']
        })
      );
    });
  });

  it('calls onClose when cancel is clicked', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(<CreateRuleDialog {...defaultProps} onClose={onClose} />);

    await act(async () => {
      await user.click(screen.getByText('cancel'));
    });

    expect(onClose).toHaveBeenCalled();
  });

  it('shows search results after triggering search', async () => {
    const user = userEvent.setup();
    mockDispatchApi.mockResolvedValueOnce({ items: [], total: 42, offset: 0, rows: 0 });
    (api.search.hit.post as ReturnType<typeof vi.fn>).mockReturnValue('search-request');

    render(<CreateRuleDialog {...defaultProps} />);

    await act(async () => {
      await user.type(screen.getByTestId('rule-query-editor'), 'event.kind:alert');
    });

    await act(async () => {
      await user.click(screen.getByTestId('rule-search-button'));
    });

    await waitFor(() => {
      expect(screen.getByTestId('query-result-text')).toBeInTheDocument();
      expect(screen.getByText(/42 results/)).toBeInTheDocument();
    });
  });

  it('shows prompt text before search is triggered', () => {
    render(<CreateRuleDialog {...defaultProps} />);

    expect(screen.getByText('hit.search.prompt')).toBeInTheDocument();
    expect(screen.queryByTestId('query-result-text')).not.toBeInTheDocument();
  });

  it('includes timeframe as ISO string when no expiry is unchecked', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    mockDispatchApi.mockResolvedValueOnce({ items: [], total: 1, offset: 0, rows: 0 });
    (api.search.hit.post as ReturnType<typeof vi.fn>).mockReturnValue('search-request');

    render(<CreateRuleDialog {...defaultProps} onSubmit={onSubmit} />);

    await act(async () => {
      await user.type(screen.getByTestId('rule-query-editor'), 'event.kind:alert');
    });

    await act(async () => {
      await user.click(screen.getByTestId('rule-search-button'));
    });

    await act(async () => {
      await user.type(screen.getByTestId('rule-destination-input'), 'alerts/incoming');
    });

    await act(async () => {
      await user.click(screen.getByTestId('rule-submit-button'));
    });

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          timeframe: expect.any(String)
        })
      );
    });
  });

  it('omits timeframe when no expiry is checked', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    mockDispatchApi.mockResolvedValueOnce({ items: [], total: 1, offset: 0, rows: 0 });
    (api.search.hit.post as ReturnType<typeof vi.fn>).mockReturnValue('search-request');

    render(<CreateRuleDialog {...defaultProps} onSubmit={onSubmit} />);

    await act(async () => {
      await user.click(screen.getByTestId('rule-no-expiry-checkbox'));
    });

    await act(async () => {
      await user.type(screen.getByTestId('rule-query-editor'), 'event.kind:alert');
    });

    await act(async () => {
      await user.click(screen.getByTestId('rule-search-button'));
    });

    await act(async () => {
      await user.type(screen.getByTestId('rule-destination-input'), 'alerts/incoming');
    });

    await act(async () => {
      await user.click(screen.getByTestId('rule-submit-button'));
    });

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          query: 'event.kind:alert',
          destination: 'alerts/incoming',
          timeframe: undefined
        })
      );
    });
  });

  it('defaults to hit index checked', () => {
    render(<CreateRuleDialog {...defaultProps} />);

    const hitCheckbox = screen.getByTestId('rule-index-hit') as HTMLInputElement;
    const observableCheckbox = screen.getByTestId('rule-index-observable') as HTMLInputElement;

    expect(hitCheckbox).toBeChecked();
    expect(observableCheckbox).not.toBeChecked();
  });

  it('includes both indexes when both are selected', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    mockDispatchApi.mockResolvedValueOnce({ items: [], total: 1, offset: 0, rows: 0 });
    (api.search.hit.post as ReturnType<typeof vi.fn>).mockReturnValue('search-request');

    render(<CreateRuleDialog {...defaultProps} onSubmit={onSubmit} />);

    await act(async () => {
      await user.click(screen.getByTestId('rule-index-observable'));
    });

    await act(async () => {
      await user.type(screen.getByTestId('rule-query-editor'), 'event.kind:alert');
    });

    await act(async () => {
      await user.click(screen.getByTestId('rule-search-button'));
    });

    await act(async () => {
      await user.type(screen.getByTestId('rule-destination-input'), 'alerts/incoming');
    });

    await act(async () => {
      await user.click(screen.getByTestId('rule-submit-button'));
    });

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          indexes: expect.arrayContaining(['hit', 'observable'])
        })
      );
    });
  });

  it('disables submit when no indexes are selected', async () => {
    const user = userEvent.setup();
    mockDispatchApi.mockResolvedValueOnce({ items: [], total: 1, offset: 0, rows: 0 });
    (api.search.hit.post as ReturnType<typeof vi.fn>).mockReturnValue('search-request');

    render(<CreateRuleDialog {...defaultProps} />);

    await act(async () => {
      await user.type(screen.getByTestId('rule-query-editor'), 'event.kind:alert');
    });

    await act(async () => {
      await user.click(screen.getByTestId('rule-search-button'));
    });

    await act(async () => {
      await user.type(screen.getByTestId('rule-destination-input'), 'alerts/incoming');
    });

    // Uncheck the default hit index
    await act(async () => {
      await user.click(screen.getByTestId('rule-index-hit'));
    });

    expect(screen.getByTestId('rule-submit-button')).toBeDisabled();
  });
});
