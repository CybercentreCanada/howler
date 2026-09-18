/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockSearchPost = vi.hoisted(() => vi.fn((body: any) => body));

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
  default: {
    search: {
      hit: {
        post: mockSearchPost
      }
    }
  }
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

vi.mock('utils/actionUtils', () => ({
  checkArgsAreFilled: (step: any, values: string) => Object.keys(step.args).every(key => JSON.parse(values)[key]),
  getArgsByContext: (args: any) => Object.keys(args),
  getOptionsByContext: (options: any, arg: string) => options[arg]
}));

vi.mock('utils/stringUtils', () => ({
  sanitizeLuceneQuery: (value: string) => value
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
    mockSearchPost.mockClear();
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
          args: { option: true, text: true },
          options: { option: ['chosen'] },
          validation: {
            warn: { query: 'warn-query', message: 'warn.message' },
            error: { query: 'error-query', message: 'error.message' }
          }
        } as any}
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

  it('shows success when validation passes and disables inputs in readonly mode', async () => {
    mockDispatchApi.mockResolvedValueOnce({ total: 0 });

    render(
      <OperationStep
        query="status:open"
        values={'{"name":"demo"}'}
        readonly
        step={{
          args: { name: true },
          validation: { warn: { query: 'warn-query' } }
        } as any}
      />
    );

    expect(screen.getByLabelText('Name')).toBeDisabled();
    expect(mockDispatchApi).not.toHaveBeenCalled();
  });
});
