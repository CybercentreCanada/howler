/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());

vi.mock('@mui/material', () => ({
  Alert: ({ children }: any) => <div>{children}</div>,
  AlertTitle: ({ children }: any) => <div>{children}</div>,
  Autocomplete: ({ value, onChange, renderInput }: any) => (
    <div>
      {renderInput({ InputProps: {} })}
      <button onClick={() => onChange(null, 'chosen')}>{value || 'choose'}</button>
    </div>
  ),
  CircularProgress: () => <div>loading</div>,
  InputAdornment: ({ children }: any) => <div>{children}</div>,
  LinearProgress: () => <div>validating</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  TextField: ({ label, value, onChange, disabled }: any) => (
    <label>
      {label}
      <input aria-label={label} value={value} onChange={onChange} disabled={disabled} />
    </label>
  )
}));

vi.mock('api', () => ({
  default: { search: { hit: { post: (body: unknown) => body } } }
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string, values?: any) => `${key}${values?.count ? `:${values.count}` : ''}` })
}));

vi.mock('react-router', () => ({
  Link: ({ to, children }: any) => <a href={to}>{children}</a>
}));

vi.mock('utils/Throttler', () => ({
  default: class {
    debounce(fn: () => void | Promise<void>) {
      void fn();
    }
  }
}));

import OperationStep from './OperationStep';

describe('OperationStep', () => {
  beforeEach(() => {
    mockDispatchApi.mockReset();
  });

  it('updates option and text fields and renders validation warnings', async () => {
    const setValues = vi.fn();
    mockDispatchApi.mockResolvedValueOnce({ total: 2 }).mockResolvedValueOnce({ total: 0 });

    render(
      <OperationStep
        query="status:open"
        values={'{"option":"initial","text":"value"}'}
        setValues={setValues}
        step={{
          args: { option: [], text: [] },
          options: { option: ['chosen'] },
          validation: {
            warn: { query: 'warn-query', message: 'warn.message' },
            error: { query: 'error-query', message: 'error.message' }
          }
        }}
      />
    );

    await waitFor(() => expect(mockDispatchApi).toHaveBeenCalledTimes(2));
    expect(screen.getByText('warn.message:2')).toBeInTheDocument();
    expect(screen.getByRole('link')).toHaveAttribute('href', '/hits?query=warn-query');

    fireEvent.click(screen.getByText('initial'));
    expect(setValues).toHaveBeenCalledWith('{"option":"chosen","text":"value"}');

    fireEvent.change(screen.getByLabelText('Text'), { target: { value: 'next' } });
    expect(setValues).toHaveBeenCalledWith('{"option":"initial","text":"next"}');
  });

  it('skips validation and disables inputs in readonly mode', () => {
    render(
      <OperationStep
        query="status:open"
        values={'{"name":"demo"}'}
        readonly
        step={{
          args: { name: [] },
          options: {},
          validation: { warn: { query: 'warn-query' } }
        }}
      />
    );

    expect(screen.getByLabelText('Name')).toBeDisabled();
    expect(mockDispatchApi).not.toHaveBeenCalled();
  });

  it.each([false, true])('renders an editable optional prompt (autocomplete: %s)', async autocomplete => {
    const setValues = vi.fn();
    mockDispatchApi.mockResolvedValueOnce({ total: 0 });

    render(
      <OperationStep
        query="status:open"
        values="{}"
        setValues={setValues}
        step={{
          args: {},
          optional_args: ['prompt'],
          options: autocomplete ? { prompt: ['chosen'] } : {},
          validation: { warn: { query: 'warn-query' } }
        }}
      />
    );

    const prompt = screen.getByLabelText('Prompt (route.actions.optional)');
    await waitFor(() => expect(screen.getByText('route.actions.alert.success')).toBeInTheDocument());
    expect(mockDispatchApi).toHaveBeenCalledTimes(1);

    if (autocomplete) {
      fireEvent.click(screen.getByText('choose'));
      expect(setValues).toHaveBeenCalledWith('{"prompt":"chosen"}');
    } else {
      fireEvent.change(prompt, { target: { value: 'Focus on suspicious process activity' } });
      expect(setValues).toHaveBeenCalledWith('{"prompt":"Focus on suspicious process activity"}');
    }
  });
});
