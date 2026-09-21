/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockGetMatchingTemplate = vi.hoisted(() => vi.fn());
const fieldContextToken = vi.hoisted(() => ({ name: 'field-context' }));
const recordSearchContextToken = vi.hoisted(() => ({ name: 'record-search-context' }));

let fieldContextValue: any;
let responseValue: any;

vi.mock('@mui/icons-material', () => ({
  Add: () => <div>add-icon</div>,
  Check: () => <div>check-icon</div>,
  Settings: () => <div>settings-icon</div>,
  TableChart: () => <div>table-icon</div>
}));

vi.mock('@mui/material', () => ({
  Autocomplete: ({ options, value, onChange, renderInput }: any) => (
    <div>
      {renderInput({})}
      <button onClick={() => onChange?.(null, options[0] ?? null)}>{value ?? 'pick-field'}</button>
    </div>
  ),
  Chip: ({ label, onClick, disabled }: any) => <button onClick={onClick} disabled={disabled}>{label}</button>,
  Divider: () => <div>divider</div>,
  Grid: ({ children }: any) => <div>{children}</div>,
  IconButton: ({ children, onClick, disabled }: any) => <button onClick={onClick} disabled={disabled}>{children}</button>,
  Stack: ({ children }: any) => <div>{children}</div>,
  TextField: ({ placeholder }: any) => <div>{placeholder}</div>
}));

vi.mock('components/app/hooks/useMatchers', () => ({
  default: () => ({ getMatchingTemplate: mockGetMatchingTemplate })
}));

vi.mock('components/app/providers/FieldProvider', () => ({
  FieldContext: fieldContextToken
}));

vi.mock('components/app/providers/RecordSearchProvider', () => ({
  RecordSearchContext: recordSearchContextToken
}));

vi.mock('components/elements/display/ChipPopper', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

vi.mock('lodash-es', () => ({
  sortBy: (values: any[], key: string) => [...values].sort((a, b) => Number(a[key]) - Number(b[key])),
  uniq: (values: string[]) => [...new Set(values)]
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('use-context-selector', () => ({
  useContextSelector: (context: any, selector: any) => {
    if (context === recordSearchContextToken) return selector({ response: responseValue });
    return undefined;
  }
}));

vi.mock('utils/typeUtils', () => ({
  isHit: (record: any) => record?.__index === 'hit'
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

import AddColumnModal from './AddColumnModal';

describe('AddColumnModal', () => {
  beforeEach(() => {
    fieldContextValue = { hitFields: [{ key: 'severity' }, { key: 'event.created' }] };
    responseValue = { items: [{ __index: 'hit', howler: { id: 'hit-1' } }, { __index: 'event', howler: { id: 'event-1' } }] };
    mockGetMatchingTemplate.mockReset().mockResolvedValue({ keys: ['severity', 'custom.field', 'custom.field'] });
  });

  it('adds explicit columns and suggested columns while disabling used suggestions', async () => {
    const addColumn = vi.fn();

    render(<AddColumnModal addColumn={addColumn} columns={['severity']} />);

    await waitFor(() => expect(mockGetMatchingTemplate).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByText('pick-field'));
    fireEvent.click(screen.getAllByText('add-icon')[0]!.parentElement!);

    expect(addColumn).toHaveBeenCalledWith('severity');
    expect(screen.getByText('severity')).toBeDisabled();

    fireEvent.click(screen.getByText('custom.field'));
    expect(addColumn).toHaveBeenCalledWith('custom.field');
  });
});
