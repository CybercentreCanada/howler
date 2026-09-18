/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());
const apiConfigContextToken = vi.hoisted(() => ({ name: 'api-config-context' }));

let configValue: any = { lookups: { 'howler.assessment': ['malicious', 'suspicious'] } };

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return {
    ...actual,
    Check: () => <div>check-icon</div>,
    Delete: () => <div>delete-icon</div>,
    Remove: () => <div>remove-icon</div>
  };
});

vi.mock('@mui/material', () => ({
  Card: ({ children }: any) => <div>{children}</div>,
  Chip: ({ label, onClick }: any) => <button onClick={onClick}>{label}</button>,
  Divider: () => <div>divider</div>,
  Grid: ({ children }: any) => <div>{children}</div>,
  IconButton: ({ children, onClick, disabled }: any) => <button disabled={disabled} onClick={onClick}>{children}</button>,
  InputAdornment: ({ children }: any) => <div>{children}</div>,
  LinearProgress: () => <div>progress</div>,
  Paper: ({ children }: any) => <div>{children}</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  Table: ({ children }: any) => <div>{children}</div>,
  TableBody: ({ children }: any) => <div>{children}</div>,
  TableCell: ({ children }: any) => <div>{children}</div>,
  TableContainer: ({ children }: any) => <div>{children}</div>,
  TableHead: ({ children }: any) => <div>{children}</div>,
  TableRow: ({ children }: any) => <div>{children}</div>,
  TextField: ({ label, value, onChange, onKeyDown }: any) => (
    <label>
      {label}
      <input aria-label={label} value={value} onChange={onChange} onKeyDown={onKeyDown} />
    </label>
  ),
  Tooltip: ({ children }: any) => <div>{children}</div>,
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('api', () => ({
  default: {
    analytic: {
      put: (id: string, payload: any) => ({ id, payload, op: 'put' })
    }
  }
}));

vi.mock('chartjs-adapter-dayjs-4', () => ({}));

vi.mock('components/app/providers/ApiConfigProvider', () => ({
  ApiConfigContext: apiConfigContextToken
}));

vi.mock('components/elements/EditRow', () => ({
  default: ({ onEdit }: any) => <button onClick={() => onEdit('true')}>toggle-skip</button>
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === apiConfigContextToken) {
        return { config: configValue };
      }
      return actual.useContext(context);
    }
  };
});

import TriageSettings from './TriageSettings';

describe('TriageSettings', () => {
  beforeEach(() => {
    configValue = { lookups: { 'howler.assessment': ['malicious', 'suspicious'] } };
    mockDispatchApi.mockReset().mockImplementation(async (_request: any) => ({ analytic_id: 'an-1' }));
  });

  it('updates skip rationale, assessments, and rationales', async () => {
    const setAnalytic = vi.fn();

    render(
      <TriageSettings
        analytic={{ analytic_id: 'an-1', triage_settings: { valid_assessments: ['malicious'], rationales: ['because'] } } as any}
        setAnalytic={setAnalytic}
      />
    );

    fireEvent.click(screen.getByText('toggle-skip'));
    await waitFor(() =>
      expect(mockDispatchApi).toHaveBeenCalledWith(
        { id: 'an-1', op: 'put', payload: { triage_settings: { skip_rationale: true } } },
        { throwError: true, showError: true }
      )
    );

    fireEvent.click(screen.getByText('Malicious'));
    await waitFor(() =>
      expect(mockDispatchApi).toHaveBeenCalledWith(
        { id: 'an-1', op: 'put', payload: { triage_settings: { valid_assessments: [] } } },
        { throwError: true, showError: true }
      )
    );

    fireEvent.click(screen.getByText('delete-icon'));
    await waitFor(() =>
      expect(mockDispatchApi).toHaveBeenCalledWith(
        { id: 'an-1', op: 'put', payload: { triage_settings: { rationales: [] } } },
        { throwError: true, showError: true }
      )
    );

    fireEvent.change(screen.getByLabelText('route.analytics.rationales.new'), { target: { value: 'new reason' } });
    fireEvent.keyDown(screen.getByLabelText('route.analytics.rationales.new'), { key: 'Enter' });
    await waitFor(() =>
      expect(mockDispatchApi).toHaveBeenCalledWith(
        { id: 'an-1', op: 'put', payload: { triage_settings: { rationales: ['because', 'new reason'] } } },
        { throwError: true, showError: true }
      )
    );

    expect(setAnalytic).toHaveBeenCalled();
  });
});
