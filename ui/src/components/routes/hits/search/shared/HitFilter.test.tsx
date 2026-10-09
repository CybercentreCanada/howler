/// <reference types="vitest" />
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useState } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiConfigContextToken = vi.hoisted(() => ({ name: 'api-config-context' }));
const fieldContextToken = vi.hoisted(() => ({ name: 'field-context' }));
const parameterContextToken = vi.hoisted(() => ({ name: 'parameter-context' }));
const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockSetSavedFilter = vi.hoisted(() => vi.fn());
const mockRemoveSavedFilter = vi.hoisted(() => vi.fn());
const mockSetFilterDisabled = vi.hoisted(() => vi.fn());
const mockFilterState = vi.hoisted(() => ({ disabledFilterIndexes: [] as number[] }));
const autocompleteProps = vi.hoisted(() => [] as any[]);
const mockAutocompleteSelection = vi.hoisted(() => ({
  value: 'normal' as 'normal' | 'clear' | 'add' | 'single' | 'unchanged'
}));

let configValue: any = { lookups: { 'howler.assessment': ['malicious'] } };

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return { ...actual, FilterList: () => <div>filter-icon</div> };
});

vi.mock('@mui/material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/material')>();
  return {
    ...actual,
    Autocomplete: (props: any) => {
      autocompleteProps.push(props);
      const { onChange, options, disabled, multiple, value, loading } = props;

      return (
        <button
          disabled={disabled}
          data-loading={Boolean(loading)}
          data-options={JSON.stringify(options)}
          onClick={() =>
            onChange(
              null,
              mockAutocompleteSelection.value === 'clear'
                ? multiple
                  ? []
                  : null
                : multiple
                  ? mockAutocompleteSelection.value === 'unchanged'
                    ? value
                    : mockAutocompleteSelection.value === 'add'
                      ? [...(value ?? []), 'added value']
                      : mockAutocompleteSelection.value === 'single'
                        ? (value ?? []).slice(0, 1)
                        : (value?.length ?? 0) > 1
                          ? [value[0], value[0]?.startsWith('C:') ? 'new\\path' : 'changed two']
                          : [value?.[0] ?? options[0] ?? 'changed one']
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
      );
    },
    Stack: ({ children }: any) => <div>{children}</div>,
    TextField: ({ label }: any) => <div>{label}</div>,
    Typography: ({ children }: any) => <div>{children}</div>
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

vi.mock('components/app/providers/FieldProvider', () => ({
  FieldContext: fieldContextToken
}));

vi.mock('components/app/providers/ParameterProvider', () => ({
  ParameterContext: parameterContextToken
}));

vi.mock('components/elements/display/ChipPopper', () => ({
  default: ({ children, icon, label, onDelete, dimmed }: any) => {
    const [open, setOpen] = useState(false);

    return (
      <div>
        <button
          className="MuiChip-root"
          data-dimmed={String(Boolean(dimmed))}
          style={{ opacity: dimmed ? 0.5 : 1 }}
          onClick={() => setOpen(current => !current)}
        >
          {icon && <span className="MuiChip-icon">{icon}</span>}
          {label}
          {onDelete && (
            <span
              className="MuiChip-deleteIcon"
              onClick={event => {
                event.stopPropagation();
                onDelete(event);
              }}
            >
              delete-filter
            </span>
          )}
        </button>
        {open && children}
      </div>
    );
  }
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('use-context-selector', () => ({
  useContextSelector: (_context: any, selector: any) =>
    selector({
      setFilter: mockSetSavedFilter,
      removeFilter: mockRemoveSavedFilter,
      disabledFilterIndexes: mockFilterState.disabledFilterIndexes,
      enableFilter: (index: number) => mockSetFilterDisabled(index, false),
      disableFilter: (index: number) => mockSetFilterDisabled(index, true)
    })
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === apiConfigContextToken) return { config: configValue };
      if (context === fieldContextToken) {
        return {
          hitFields: [
            { key: 'howler.assessment' },
            { key: 'howler.escalation' },
            { key: 'howler.analytic' },
            { key: 'howler.detection' },
            { key: 'event.provider' },
            { key: 'organization.name' }
          ],
          getHitFields: vi.fn()
        };
      }
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
    mockSetFilterDisabled.mockReset().mockImplementation((index: number, disabled: boolean) => {
      mockFilterState.disabledFilterIndexes = disabled ? [index] : [];
    });
    mockFilterState.disabledFilterIndexes = [];
    autocompleteProps.length = 0;
    mockAutocompleteSelection.value = 'normal';
  });

  it('initializes from value, fetches custom lookups, updates values, and removes filters', async () => {
    render(<HitFilter id={1} value={'howler.assessment:*'} />);
    await waitFor(() => expect(mockSetSavedFilter).toHaveBeenCalledWith(1, 'howler.assessment:*'));

    fireEvent.click(screen.getByRole('button', { name: /howler.assessment:\*/ }));
    fireEvent.click(screen.getAllByText('change-filter')[0]);
    await waitFor(() =>
      expect(mockDispatchApi).toHaveBeenCalledWith(
        { query: 'event.provider:*', fields: ['event.provider'], rows: 100 },
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

  it('temporarily disables and re-enables the chip without editing its saved filter', () => {
    const value = 'howler.assessment:"malicious"';
    const { rerender } = render(<HitFilter id={13} value={value} />);
    const chip = screen.getByRole('button', { name: /howler.assessment:/ });

    expect(chip).toHaveStyle({ opacity: '1' });
    fireEvent.click(chip);

    const disableControl = screen.getByRole('checkbox', { name: 'hit.search.filter.disable' });
    expect(disableControl).not.toBeChecked();
    fireEvent.click(disableControl);
    expect(mockSetFilterDisabled).toHaveBeenLastCalledWith(13, true);
    expect(mockFilterState.disabledFilterIndexes).toEqual([13]);

    rerender(<HitFilter id={13} value={value} size="medium" />);
    const disabledChip = screen.getByRole('button', { name: /howler.assessment:/ });
    expect(disabledChip).toHaveAttribute('data-dimmed', 'true');
    expect(disabledChip).toHaveStyle({ opacity: '0.5' });
    expect(screen.getByRole('checkbox', { name: 'hit.search.filter.disable' })).toBeChecked();

    fireEvent.click(screen.getByRole('checkbox', { name: 'hit.search.filter.disable' }));
    expect(mockSetFilterDisabled).toHaveBeenLastCalledWith(13, false);

    rerender(<HitFilter id={13} value={value} />);
    const reenabledChip = screen.getByRole('button', { name: /howler.assessment:/ });
    expect(reenabledChip).toHaveAttribute('data-dimmed', 'false');
    expect(reenabledChip).toHaveStyle({ opacity: '1' });
    expect(screen.getByRole('checkbox', { name: 'hit.search.filter.disable' })).not.toBeChecked();
    expect(mockSetSavedFilter).toHaveBeenLastCalledWith(13, value);
  });

  it('commits a field change immediately while retaining negation', () => {
    render(<HitFilter id={13} value={'-howler.assessment:"malicious"'} />);
    fireEvent.click(screen.getByRole('button', { name: /howler.assessment:/ }));
    fireEvent.click(screen.getAllByText('change-filter')[0]);

    expect(mockSetSavedFilter).toHaveBeenLastCalledWith(13, '-event.provider:*');
    expect(screen.getByRole('button', { name: /event.provider:\*/ })).toBeInTheDocument();
  });

  it('does not reset an edited filter when lookup configuration changes', () => {
    const { rerender } = render(<HitFilter id={14} value={'event.provider:"a"'} />);
    fireEvent.click(screen.getByRole('button', { name: /event.provider:/ }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'hit.search.filter.exclude' }));
    mockSetSavedFilter.mockClear();

    configValue = { lookups: { 'event.provider': ['a'] } };
    rerender(<HitFilter id={14} value={'event.provider:"a"'} size="medium" />);

    expect(screen.getByRole('checkbox', { name: 'hit.search.filter.exclude' })).toBeChecked();
    expect(mockSetSavedFilter).not.toHaveBeenCalled();
  });

  it('uses configured lookups and wildcard values', async () => {
    render(<HitFilter id={2} value={'howler.assessment:*'} />);
    await waitFor(() => expect(mockSetSavedFilter).toHaveBeenCalledWith(2, 'howler.assessment:*'));
  });

  it('shows only default fields until the user searches for another indexed field', () => {
    render(<HitFilter id={3} value="howler.assessment:*" />);
    fireEvent.click(screen.getByRole('button', { name: /howler.assessment:\*/ }));

    const getFieldAutocomplete = () =>
      [...autocompleteProps].reverse().find(props => props.options.includes('organization.name'))!;
    const autocompleteState = {
      inputValue: 'howler.assessment',
      getOptionLabel: (option: string) => option
    };

    let fieldAutocomplete = getFieldAutocomplete();
    expect(fieldAutocomplete.filterOptions(fieldAutocomplete.options, autocompleteState)).toEqual([
      'howler.assessment',
      'howler.escalation',
      'howler.analytic',
      'howler.detection',
      'event.provider'
    ]);

    act(() => fieldAutocomplete.onInputChange(null, 'organization', 'input'));
    fieldAutocomplete = getFieldAutocomplete();
    expect(fieldAutocomplete.filterOptions(fieldAutocomplete.options, autocompleteState)).toEqual([
      'organization.name'
    ]);

    act(() => fieldAutocomplete.onInputChange(null, 'howler.assessment', 'reset'));
    fieldAutocomplete = getFieldAutocomplete();
    expect(fieldAutocomplete.filterOptions(fieldAutocomplete.options, autocompleteState)).toEqual([
      'howler.assessment',
      'howler.escalation',
      'howler.analytic',
      'howler.detection',
      'event.provider'
    ]);
  });

  it('deduplicates decoded literals while preserving quoted OR text', () => {
    const clause = String.raw`event.provider:("a" OR "\a" OR "text OR more" OR "escaped\"quote")`;
    render(<HitFilter id={15} value={clause} />);
    fireEvent.click(screen.getByRole('button', { name: /event.provider:/ }));
    mockAutocompleteSelection.value = 'unchanged';
    fireEvent.click(screen.getAllByText('change-filter')[1]);

    expect(mockSetSavedFilter).toHaveBeenLastCalledWith(
      15,
      String.raw`event.provider:("a" OR "text OR more" OR "escaped\"quote")`
    );
  });

  it('collapses duplicate values to a canonical scalar while preserving negation', () => {
    render(<HitFilter id={20} value={String.raw`-event.provider:("\a" OR "a" OR "a")`} />);
    fireEvent.click(screen.getByRole('button', { name: /event.provider:/ }));
    mockAutocompleteSelection.value = 'unchanged';
    fireEvent.click(screen.getAllByText('change-filter')[1]);

    expect(mockSetSavedFilter).toHaveBeenLastCalledWith(20, '-event.provider:"a"');
  });

  it.each(['plain', String.raw`"\plain"`, '"constructor"', '"__proto__"'])(
    'canonically quotes a decoded scalar from %s',
    literal => {
      render(<HitFilter id={21} value={`event.provider:${literal}`} />);
      fireEvent.click(screen.getByRole('button', { name: /event.provider:/ }));
      mockAutocompleteSelection.value = 'unchanged';
      fireEvent.click(screen.getAllByText('change-filter')[1]);

      const expected = literal.includes('plain') ? 'plain' : literal.slice(1, -1);
      expect(mockSetSavedFilter).toHaveBeenLastCalledWith(21, `event.provider:"${expected}"`);
    }
  );

  it('accepts whitespace-separated quoted OR values', () => {
    render(<HitFilter id={16} value={'event.provider:( "a"\tOR\n"b" )'} />);
    fireEvent.click(screen.getByRole('button', { name: /event.provider:/ }));
    mockAutocompleteSelection.value = 'unchanged';
    fireEvent.click(screen.getAllByText('change-filter')[1]);

    expect(mockSetSavedFilter).toHaveBeenLastCalledWith(16, 'event.provider:("a" OR "b")');
  });

  it('synchronizes externally replaced filters', () => {
    const { rerender } = render(<HitFilter id={17} value={'event.provider:"a"'} />);
    rerender(<HitFilter id={17} value={'-howler.assessment:*'} />);
    fireEvent.click(screen.getByRole('button', { name: /howler.assessment:/ }));

    expect(screen.getByRole('checkbox', { name: 'hit.search.filter.exclude' })).toBeChecked();
    expect(mockSetSavedFilter).toHaveBeenLastCalledWith(17, '-howler.assessment:*');
  });

  it('settles failed lookup requests without disabling free-text editing', async () => {
    mockDispatchApi.mockRejectedValueOnce(new Error('offline'));
    render(<HitFilter id={18} value={'event.provider:*'} />);
    fireEvent.click(screen.getByRole('button', { name: /event.provider:/ }));

    const values = screen.getAllByText('change-filter')[1];
    await waitFor(() => expect(values).toHaveAttribute('data-loading', 'false'));
    expect(values).not.toBeDisabled();
    expect(values).toHaveAttribute('data-options', '[]');
    expect(mockSetSavedFilter).toHaveBeenCalledWith(18, 'event.provider:*');
  });

  it('ignores stale lookup responses after switching to a configured field', async () => {
    let resolveFacets!: (facets: { 'event.provider': { stale: number } }) => void;
    mockDispatchApi.mockImplementationOnce(
      () =>
        new Promise(resolve => {
          resolveFacets = resolve;
        })
    );
    const { rerender } = render(<HitFilter id={19} value={'event.provider:*'} />);
    await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
    rerender(<HitFilter id={19} value={'howler.assessment:*'} />);
    fireEvent.click(screen.getByRole('button', { name: /howler.assessment:/ }));
    await act(async () => resolveFacets({ 'event.provider': { stale: 1 } }));

    const values = screen.getAllByText('change-filter')[1];
    expect(values).toHaveAttribute('data-options', '["malicious"]');
    expect(values).toHaveAttribute('data-loading', 'false');
  });

  it('loads custom lookups when initialized with a custom category', async () => {
    render(<HitFilter id={11} value={'event.provider:"azure"'} />);

    fireEvent.click(screen.getByRole('button', { name: /event.provider:/ }));
    await waitFor(() =>
      expect(mockDispatchApi).toHaveBeenCalledWith(
        { query: 'event.provider:*', fields: ['event.provider'], rows: 100 },
        { throwError: false }
      )
    );

    fireEvent.click(screen.getAllByText('change-filter')[1]);
    expect(mockSetSavedFilter).toHaveBeenLastCalledWith(11, 'event.provider:"azure"');
  });

  it('uses the clear action to set a scalar filter to wildcard', () => {
    render(<HitFilter id={9} value={'howler.assessment:"malicious"'} />);
    fireEvent.click(screen.getByRole('button', { name: /howler.assessment:/ }));

    mockAutocompleteSelection.value = 'clear';
    fireEvent.click(screen.getAllByText('change-filter')[1]);
    expect(mockSetSavedFilter).toHaveBeenLastCalledWith(9, 'howler.assessment:*');
  });

  it('uses the clear action to set grouped filters to wildcard', () => {
    render(<HitFilter id={10} value={'event.provider:("a" OR "b")'} />);
    fireEvent.click(screen.getByRole('button', { name: /event.provider:/ }));

    mockAutocompleteSelection.value = 'clear';
    fireEvent.click(screen.getAllByText('change-filter')[1]);

    expect(mockSetSavedFilter).toHaveBeenLastCalledWith(10, 'event.provider:*');
  });

  it('serializes selections by their current cardinality', () => {
    render(<HitFilter id={12} value={'event.provider:"a"'} />);
    fireEvent.click(screen.getByRole('button', { name: /event.provider:/ }));

    mockAutocompleteSelection.value = 'add';
    fireEvent.click(screen.getAllByText('change-filter')[1]);
    expect(mockSetSavedFilter).toHaveBeenLastCalledWith(12, 'event.provider:("a" OR "added value")');

    mockAutocompleteSelection.value = 'single';
    fireEvent.click(screen.getAllByText('change-filter')[1]);
    expect(mockSetSavedFilter).toHaveBeenLastCalledWith(12, 'event.provider:"a"');
  });

  it('toggles negation without losing a grouped OR clause', async () => {
    const { container } = render(<HitFilter id={3} value={'event.provider:("a" OR "b")'} />);

    const chip = screen.getByRole('button', { name: /event.provider:/ });
    fireEvent.click(chip);
    const toggle = screen.getByRole('checkbox', { name: 'hit.search.filter.exclude' });
    expect(chip).toHaveClass('MuiChip-root');
    expect(toggle).not.toBeChecked();
    fireEvent.click(toggle);

    expect(mockSetSavedFilter).toHaveBeenLastCalledWith(3, '-event.provider:("a" OR "b")');
    expect(screen.getByRole('button', { name: /event.provider:/ })).toBeInTheDocument();
    expect(container.querySelector('.MuiChip-icon [data-testid="RemoveCircleOutlineIcon"]')).not.toBeNull();
    expect(toggle).toBeChecked();
    fireEvent.click(toggle);
    expect(mockSetSavedFilter).toHaveBeenLastCalledWith(3, 'event.provider:("a" OR "b")');
  });

  it.each([
    'event.created:[a TO z]',
    'event.enabled:true',
    'other OR event.provider:"a"',
    'event.provider:NOT',
    'event.provider:("a" OR )',
    'event.provider:("a" AND "b")',
    'event.provider:"unterminated',
    'free text'
  ])('toggles unsupported clauses without rewriting %s', clause => {
    render(<HitFilter id={5} value={clause} />);

    expect(screen.getByText(clause)).toBeInTheDocument();
    fireEvent.click(screen.getByText(clause).closest('.MuiChip-root')!);
    expect(screen.getAllByText('change-filter').every(button => (button as HTMLButtonElement).disabled)).toBe(true);
    fireEvent.click(screen.getByRole('checkbox', { name: 'hit.search.filter.exclude' }));

    expect(mockSetSavedFilter).toHaveBeenLastCalledWith(5, `-${clause}`);
  });

  it('preserves an escaped literal star when toggling negation', () => {
    const clause = 'event.provider:"\\*"';
    render(<HitFilter id={6} value={clause} />);

    fireEvent.click(screen.getByRole('button', { name: /event.provider:/ }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'hit.search.filter.exclude' }));

    expect(mockSetSavedFilter).toHaveBeenLastCalledWith(6, `-${clause}`);
  });

  it('keeps an escaped literal star when recommitting a negative scalar filter', () => {
    const clause = '-event.provider:"\\*"';
    render(<HitFilter id={7} value={clause} />);

    fireEvent.click(screen.getByRole('button', { name: /event.provider:/ }));
    fireEvent.click(screen.getAllByText('change-filter')[1]);

    expect(mockSetSavedFilter).toHaveBeenLastCalledWith(7, clause);
  });

  it('retains negation and grouped values when editing a grouped filter', async () => {
    render(<HitFilter id={4} value={'-event.provider:("a" OR "b")'} />);

    fireEvent.click(screen.getByRole('button', { name: /event.provider:/ }));
    fireEvent.click(screen.getAllByText('change-filter')[1]);

    expect(mockSetSavedFilter).toHaveBeenLastCalledWith(4, '-event.provider:("a" OR "changed two")');
  });

  it('canonically escapes paths without losing literal backslashes when editing a grouped filter', () => {
    const clause = String.raw`-event.provider:("C:\\logs" OR "other")`;
    render(<HitFilter id={8} value={clause} />);

    fireEvent.click(screen.getByRole('button', { name: /event.provider:/ }));
    fireEvent.click(screen.getAllByText('change-filter')[1]);

    expect(mockSetSavedFilter).toHaveBeenLastCalledWith(8, String.raw`-event.provider:("C\:\\logs" OR "new\\path")`);
  });
});
