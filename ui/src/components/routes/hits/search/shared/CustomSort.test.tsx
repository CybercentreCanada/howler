/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const fieldContextToken = vi.hoisted(() => ({ name: 'field-context' }));
const parameterContextToken = vi.hoisted(() => ({ name: 'parameter-context' }));
const mockGetHitFields = vi.hoisted(() => vi.fn());
const mockSetSavedSort = vi.hoisted(() => vi.fn());

let fieldContextValue: any = { hitFields: [{ key: 'event.created' }, { key: 'howler.score' }], getHitFields: mockGetHitFields };
let parameterValue: any = { sort: 'event.created desc', setSort: mockSetSavedSort };

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return {
    ...actual,
    ArrowDownward: () => <div>down-icon</div>,
    ArrowUpward: () => <div>up-icon</div>,
    Cancel: () => <div>cancel-icon</div>
  };
});

vi.mock('@mui/material', () => ({
  Autocomplete: ({ onChange, options }: any) => <button onClick={() => onChange(null, options[1])}>pick-field</button>,
  Chip: ({ label, onClick, onDelete }: any) => <div><button onClick={onClick}>{label}</button><button onClick={onDelete}>delete-{label}</button></div>,
  Grid: ({ children }: any) => <div>{children}</div>,
  MenuItem: ({ children }: any) => <div>{children}</div>,
  Select: ({ value, onChange }: any) => <button onClick={() => onChange({ target: { value: value === 'desc' ? 'asc' : 'desc' } })}>toggle-direction</button>,
  Stack: ({ children }: any) => <div>{children}</div>,
  TextField: ({ label }: any) => <div>{label}</div>
}));

vi.mock('components/app/providers/FieldProvider', () => ({
  FieldContext: fieldContextToken
}));

vi.mock('components/app/providers/ParameterProvider', () => ({
  ParameterContext: parameterContextToken
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('use-context-selector', () => ({
  useContextSelector: (_context: any, selector: any) => selector({ sort: parameterValue.sort, setSort: mockSetSavedSort })
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === fieldContextToken) return fieldContextValue;
      return actual.useContext(context);
    }
  };
});

import CustomSort from './CustomSort';

describe('CustomSort', () => {
  beforeEach(() => {
    fieldContextValue = { hitFields: [{ key: 'event.created' }, { key: 'howler.score' }], getHitFields: mockGetHitFields };
    parameterValue = { sort: 'event.created desc', setSort: mockSetSavedSort };
    mockGetHitFields.mockReset();
    mockSetSavedSort.mockReset();
  });

  it('loads hit fields, adds sort entries, toggles direction, and deletes entries', async () => {
    render(<CustomSort />);
    await waitFor(() => expect(mockGetHitFields).toHaveBeenCalled());

    fireEvent.click(screen.getByText('toggle-direction'));
    fireEvent.click(screen.getByText('pick-field'));
    await waitFor(() => expect(mockSetSavedSort).toHaveBeenCalledWith('event.created desc,howler.score asc'));

    fireEvent.click(screen.getByText('event.created'));
    expect(mockSetSavedSort).toHaveBeenCalledWith('event.created asc');

    fireEvent.click(screen.getByText('delete-event.created'));
    expect(mockSetSavedSort).toHaveBeenCalledWith('');
  });
});
