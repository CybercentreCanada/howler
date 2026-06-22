import { render, screen } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import type { PropsWithChildren } from 'react';
import { setupContextSelectorMock } from 'tests/mocks';
import { beforeEach, describe, expect, it, vi } from 'vitest';

setupContextSelectorMock();

const mockIndexPickerProps = vi.hoisted(() => ({
  last: null as null | { additionalOptions?: { label: string; value: string }[]; defaultIndexes?: string[] }
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key
  })
}));

vi.mock('components/routes/hits/search/shared/IndexPicker', () => ({
  default: (props: { additionalOptions?: { label: string; value: string }[]; defaultIndexes?: string[] }) => {
    mockIndexPickerProps.last = props;
    return <div id="index-picker" />;
  }
}));

import { ParameterContext } from 'components/app/providers/ParameterProvider';
import FuzzySearchBar from './FuzzySearchBar';

const mockOnSearch = vi.fn();
const mockSetQuery = vi.fn();

const parameterContextValue = {
  indexes: ['hit', 'case'] as string[],
  query: '',
  setQuery: mockSetQuery
};

const Wrapper = ({ children }: PropsWithChildren) => {
  return <ParameterContext.Provider value={parameterContextValue as any}>{children}</ParameterContext.Provider>;
};

describe('FuzzySearchBar', () => {
  let user: UserEvent;

  beforeEach(() => {
    user = userEvent.setup();
    vi.clearAllMocks();
    parameterContextValue.indexes = ['hit', 'case'];
    parameterContextValue.query = '';
    mockIndexPickerProps.last = null;
  });

  it('renders search input and index picker', () => {
    render(<FuzzySearchBar onSearch={mockOnSearch} />, { wrapper: Wrapper });

    expect(screen.getByTestId('fuzzy-search-input')).toBeInTheDocument();
    expect(screen.getByTestId('index-picker')).toBeInTheDocument();
  });

  it('disables search button when query is empty', () => {
    render(<FuzzySearchBar onSearch={mockOnSearch} />, { wrapper: Wrapper });

    expect(screen.getByTestId('fuzzy-search-button')).toBeDisabled();
  });

  it('calls setQuery and onSearch with trimmed query and selected indexes on click', async () => {
    render(<FuzzySearchBar onSearch={mockOnSearch} />, { wrapper: Wrapper });

    await user.type(screen.getByRole('textbox'), '  malware triage  ');
    await user.click(screen.getByTestId('fuzzy-search-button'));

    expect(mockSetQuery).toHaveBeenCalledWith('malware triage');
    expect(mockOnSearch).toHaveBeenCalledWith('malware triage', ['hit', 'case']);
  });

  it('triggers search on Enter key', async () => {
    render(<FuzzySearchBar onSearch={mockOnSearch} />, { wrapper: Wrapper });

    await user.type(screen.getByRole('textbox'), 'suspicious ip{enter}');

    expect(mockSetQuery).toHaveBeenCalledWith('suspicious ip');
    expect(mockOnSearch).toHaveBeenCalledWith('suspicious ip', ['hit', 'case']);
  });

  it('does not call search for whitespace-only input', async () => {
    render(<FuzzySearchBar onSearch={mockOnSearch} />, { wrapper: Wrapper });

    await user.type(screen.getByRole('textbox'), '   ');
    expect(screen.getByTestId('fuzzy-search-button')).toBeDisabled();

    expect(mockSetQuery).not.toHaveBeenCalled();
    expect(mockOnSearch).not.toHaveBeenCalled();
  });

  it('shows loading spinner and hides search button when loading', () => {
    render(<FuzzySearchBar onSearch={mockOnSearch} loading />, { wrapper: Wrapper });

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
    expect(screen.queryByTestId('fuzzy-search-button')).not.toBeInTheDocument();
  });

  it('passes expected options to IndexPicker', () => {
    render(<FuzzySearchBar onSearch={mockOnSearch} />, { wrapper: Wrapper });

    expect(mockIndexPickerProps.last).toEqual({
      additionalOptions: [{ label: 'hit.search.index.case', value: 'case' }],
      defaultIndexes: ['hit', 'observable', 'case']
    });
  });

  it('initializes input with default query from context', () => {
    parameterContextValue.query = 'existing search';
    render(<FuzzySearchBar onSearch={mockOnSearch} />, { wrapper: Wrapper });

    expect(screen.getByRole('textbox')).toHaveValue('existing search');
  });
});
