/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiConfigContextToken = vi.hoisted(() => ({ name: 'api-config-context' }));
const parameterContextToken = vi.hoisted(() => ({ name: 'parameter-context' }));
const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockSetSavedFilter = vi.hoisted(() => vi.fn());
const mockRemoveSavedFilter = vi.hoisted(() => vi.fn());
const mockAutocompleteSelection = vi.hoisted(() => ({ value: 'normal' as 'normal' | 'wildcard' | 'clear' }));

let configValue: any = { lookups: { 'howler.assessment': ['malicious'] } };

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return { ...actual, FilterList: () => <div>filter-icon</div> };
});

vi.mock('@mui/material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/material')>();
  return {
    ...actual,
    Autocomplete: ({ onChange, options, disabled, multiple, value }: any) => (
      <button
        disabled={disabled}
        onClick={() =>
          onChange(
            null,
            mockAutocompleteSelection.value === 'wildcard'
              ? options.at(-1)
              : mockAutocompleteSelection.value === 'clear'
                ? null
                : multiple
                  ? [value?.[0] ?? 'changed one', value?.[0]?.startsWith('C:') ? 'new\\path' : 'changed two']
                  : value === '*'
                    ? '*'
                    : options.includes('event.provider')
                      ? 'event.provider'
                      : options[0]
          )
        }
      >
        change-filter
      </button>
    )
  };
});

vi.mock('api', () => ({
  default: {
    search: {
      facet: {
        hit: {
          post: (body: any) => body
        }
      }
    }
  }
}));

vi.mock('components/app/providers/ApiConfigProvider', () => ({
  ApiConfigContext: apiConfigContextToken
}));

vi.mock('components/app/providers/ParameterProvider', () => ({
  ParameterContext: parameterContextToken
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('use-context-selector', () => ({
  useContextSelector: (_context: any, selector: any) =>
    selector({ setFilter: mockSetSavedFilter, removeFilter: mockRemoveSavedFilter })
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === apiConfigContextToken) return { config: configValue };
      return actual.useContext(context);
    }
  };
});

import HitFilter from './HitFilter';

describe('HitFilter', () => {
  beforeEach(() => {
    configValue = { lookups: { 'howler.assessment': ['malicious'] } };
    mockDispatchApi.mockReset().mockImplementation(async _value => ({ 'event.provider': { azure: 2 } }));
    mockSetSavedFilter.mockReset();
    mockRemoveSavedFilter.mockReset();
    mockAutocompleteSelection.value = 'normal';
  });

  it('initializes from value, fetches custom lookups, updates values, and removes filters', async () => {
    render(<HitFilter id={1} value={'howler.assessment:*'} />);
    await waitFor(() => expect(mockSetSavedFilter).toHaveBeenCalledWith(1, 'howler.assessment:*'));

    fireEvent.click(screen.getByRole('button', { name: /howler.assessment:\*/ }));
    fireEvent.click(screen.getAllByText('change-filter')[0]);
    await waitFor(() =>
      expect(mockDispatchApi).toHaveBeenCalledWith(
        { query: 'howler.id:*', fields: ['event.provider'], rows: 100 },
        { throwError: false }
      )
    );

    fireEvent.click(screen.getAllByText('change-filter')[1]);
    expect(mockSetSavedFilter).toHaveBeenCalledWith(1, 'event.provider:"azure"');

    const chip = screen.getByRole('button', { name: /event.provider:"azure"/ });
    const deleteIcon = chip.querySelector('.MuiChip-deleteIcon');
    expect(deleteIcon).not.toBeNull();
    fireEvent.click(deleteIcon!);
    expect(mockRemoveSavedFilter).toHaveBeenCalledWith('howler.assessment:*');
  });

  it('uses configured lookups and wildcard values', async () => {
    render(<HitFilter id={2} value={'howler.assessment:*'} />);
    await waitFor(() => expect(mockSetSavedFilter).toHaveBeenCalledWith(2, 'howler.assessment:*'));
  });

  it('keeps the explicit wildcard option and clearing as placeholders', () => {
    render(<HitFilter id={9} value={'howler.assessment:"malicious"'} />);
    fireEvent.click(screen.getByRole('button', { name: /howler.assessment:/ }));

    mockAutocompleteSelection.value = 'wildcard';
    fireEvent.click(screen.getAllByText('change-filter')[1]);
    expect(mockSetSavedFilter).toHaveBeenLastCalledWith(9, 'howler.assessment:*');

    mockAutocompleteSelection.value = 'clear';
    fireEvent.click(screen.getAllByText('change-filter')[1]);
    expect(mockSetSavedFilter).toHaveBeenLastCalledWith(9, 'howler.assessment:*');
  });

  it('toggles negation without losing a grouped OR clause', async () => {
    render(<HitFilter id={3} value={'event.provider:("a" OR "b")'} />);

    const chip = screen.getByRole('button', { name: /event.provider:/ });
    const toggle = screen.getByRole('button', { name: 'hit.search.filter.exclude' });
    expect(chip).toHaveClass('MuiChip-root');
    expect(chip).not.toContainElement(toggle);
    fireEvent.click(toggle);

    expect(mockSetSavedFilter).toHaveBeenLastCalledWith(3, '-event.provider:("a" OR "b")');
    expect(screen.getByRole('button', { name: /-event.provider:/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'hit.search.filter.include' })).toBeInTheDocument();
  });

  it.each(['event.created:[a TO z]', 'event.enabled:true'])(
    'toggles unsupported clauses without rewriting %s',
    clause => {
      render(<HitFilter id={5} value={clause} />);

      expect(screen.getByText(clause)).toBeInTheDocument();
      fireEvent.click(screen.getByText(clause).closest('.MuiChip-root')!);
      expect(screen.getAllByText('change-filter').every(button => (button as HTMLButtonElement).disabled)).toBe(true);
      fireEvent.click(screen.getByRole('button', { name: 'hit.search.filter.exclude' }));

      expect(mockSetSavedFilter).toHaveBeenLastCalledWith(5, `-${clause}`);
    }
  );

  it('preserves an escaped literal star when toggling negation', () => {
    const clause = 'event.provider:"\\*"';
    render(<HitFilter id={6} value={clause} />);

    fireEvent.click(screen.getByRole('button', { name: 'hit.search.filter.exclude' }));

    expect(mockSetSavedFilter).toHaveBeenLastCalledWith(6, `-${clause}`);
  });

  it('keeps an escaped literal star when recommitting a negative scalar filter', () => {
    const clause = '-event.provider:"\\*"';
    render(<HitFilter id={7} value={clause} />);

    fireEvent.click(screen.getByRole('button', { name: /-event.provider:/ }));
    fireEvent.click(screen.getAllByText('change-filter')[1]);

    expect(mockSetSavedFilter).toHaveBeenLastCalledWith(7, clause);
  });

  it('retains negation and grouped values when editing a grouped filter', async () => {
    render(<HitFilter id={4} value={'-event.provider:("a" OR "b")'} />);

    fireEvent.click(screen.getByRole('button', { name: /-event.provider:/ }));
    fireEvent.click(screen.getAllByText('change-filter')[1]);

    expect(mockSetSavedFilter).toHaveBeenLastCalledWith(4, '-event.provider:("a" OR "changed two")');
  });

  it('round-trips an untouched escaped backslash when editing a grouped filter', () => {
    const clause = String.raw`-event.provider:("C:\\logs" OR "other")`;
    render(<HitFilter id={8} value={clause} />);

    fireEvent.click(screen.getByRole('button', { name: /-event.provider:/ }));
    fireEvent.click(screen.getAllByText('change-filter')[1]);

    expect(mockSetSavedFilter).toHaveBeenLastCalledWith(8, String.raw`-event.provider:("C:\\logs" OR "new\\path")`);
  });
});
