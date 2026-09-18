/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockShowInfoMessage = vi.hoisted(() => vi.fn());
const mockApiKeyPost = vi.hoisted(() => vi.fn((name: string, privs: string[], expiry: string) => ({ name, privs, expiry })));
const apiConfigContextToken = vi.hoisted(() => ({ name: 'api-config-context' }));

let configValue: any = {
  configuration: {
    auth: {
      max_apikey_duration_amount: 1,
      max_apikey_duration_unit: 'days',
      allow_extended_apikeys: true
    }
  }
};

vi.mock('@mui/material', () => ({
  Alert: ({ children }: any) => <div>{children}</div>,
  AlertTitle: ({ children }: any) => <div>{children}</div>,
  Button: ({ children, onClick, disabled }: any) => <button disabled={disabled} onClick={onClick}>{children}</button>,
  Checkbox: ({ onChange }: any) => <input aria-label="checkbox" type="checkbox" onChange={onChange} />,
  Divider: () => <div>divider</div>,
  FormControl: ({ children }: any) => <div>{children}</div>,
  FormControlLabel: ({ control, label }: any) => <label>{control}{label}</label>,
  FormGroup: ({ children }: any) => <div>{children}</div>,
  FormLabel: ({ children }: any) => <div>{children}</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  TextField: ({ label, value, onChange, inputProps, size }: any) => (
    <label>
      {label ?? size ?? 'text'}
      <input aria-label={label ?? size ?? 'text'} value={value} onChange={onChange} readOnly={inputProps?.readOnly} />
    </label>
  ),
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('@mui/x-date-pickers', () => ({
  LocalizationProvider: ({ children }: any) => <>{children}</>,
  StaticDateTimePicker: ({ value, onChange }: any) => (
    <button onClick={() => onChange({ toISOString: () => '2027-01-01T00:00:00.000Z' })}>{value ? 'change-date' : 'set-date'}</button>
  )
}));

vi.mock('@mui/x-date-pickers/AdapterDayjs', () => ({
  AdapterDayjs: class {}
}));

vi.mock('api', () => ({
  default: {
    auth: {
      apikey: {
        post: mockApiKeyPost
      }
    }
  }
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('components/hooks/useMySnackbar', () => ({
  default: () => ({ showInfoMessage: mockShowInfoMessage })
}));

vi.mock('dayjs', () => {
  const factory = () => ({
    add: () => ({ toISOString: () => '2026-09-19T00:00:00.000Z', format: () => 'Sep 19 00:00:00' })
  });
  (factory as any).duration = (amount: number, unit: string) => ({
    asSeconds: () => (unit === 'days' ? amount * 86400 : amount)
  });
  return { default: factory };
});

vi.mock('react-i18next', () => ({
  Trans: ({ i18nKey }: any) => <>{i18nKey}</>,
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('../providers/ApiConfigProvider', () => ({
  ApiConfigContext: apiConfigContextToken
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

import ApiKeyDrawer from './ApiKeyDrawer';

describe('ApiKeyDrawer', () => {
  beforeEach(() => {
    configValue = {
      configuration: {
        auth: {
          max_apikey_duration_amount: 1,
          max_apikey_duration_unit: 'days',
          allow_extended_apikeys: true
        }
      }
    };
    mockDispatchApi.mockReset();
    mockShowInfoMessage.mockReset();
    mockApiKeyPost.mockClear();
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) }
    });
  });

  it('validates input, creates a key, and copies the generated value', async () => {
    const onCreated = vi.fn();
    mockDispatchApi.mockResolvedValueOnce({ apikey: 'demo-key:secret' });

    render(<ApiKeyDrawer onCreated={onCreated} />);

    expect(screen.getByText('app.drawer.user.apikey.limit.title')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('app.drawer.user.apikey.field.name'), { target: { value: 'bad-name!' } });
    expect(screen.getByLabelText('app.drawer.user.apikey.field.name')).toHaveValue('');

    fireEvent.change(screen.getByLabelText('app.drawer.user.apikey.field.name'), { target: { value: 'demo_key' } });
    fireEvent.click(screen.getAllByLabelText('checkbox')[0]!);
    fireEvent.click(screen.getByText('change-date'));
    fireEvent.click(screen.getByText('button.create'));

    await waitFor(() =>
      expect(mockDispatchApi).toHaveBeenCalledWith(
        { name: 'demo_key', privs: ['R'], expiry: '2027-01-01T00:00:00.000Z' },
        { throwError: true, showError: true }
      )
    );
    expect(onCreated).toHaveBeenCalledWith('demo-key', ['R'], '2027-01-01T00:00:00.000Z', 'demo-key:secret');
    expect(screen.getByDisplayValue('demo-key:secret')).toBeInTheDocument();

    fireEvent.click(screen.getByText('button.copy'));
    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalledWith('demo-key:secret'));
    expect(mockShowInfoMessage).toHaveBeenCalledWith('drawer.apikey.copied');
  });
});
