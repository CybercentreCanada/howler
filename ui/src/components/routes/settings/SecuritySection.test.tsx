/// <reference types="vitest" />
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiConfigContextToken = vi.hoisted(() => ({ name: 'api-config-context' }));
const mockExecuteFunction = vi.hoisted(() => vi.fn());
const mockGet = vi.hoisted(() => vi.fn());

let configValue: any = { config: { configuration: { auth: { allow_apikeys: true } } } };

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return {
    ...actual,
    Add: () => <div>add-icon</div>
  };
});

vi.mock('@mui/material', () => ({
  Chip: ({ label, onDelete }: any) => <button onClick={onDelete}>{label}</button>,
  Grid: ({ children }: any) => <div>{children}</div>,
  IconButton: ({ children, onClick }: any) => <button onClick={onClick}>{children}</button>,
  TableCell: ({ children }: any) => <div>{children}</div>,
  TableRow: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/app/providers/ApiConfigProvider', () => ({
  ApiConfigContext: apiConfigContextToken
}));

vi.mock('components/hooks/useMyLocalStorage', () => ({
  default: () => ({ get: mockGet })
}));

vi.mock('plugins/store', () => ({
  default: { plugins: ['demo'] }
}));

vi.mock('react-i18next', () => ({
  Trans: ({ i18nKey }: any) => <span>{i18nKey}</span>,
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-pluggable', () => ({
  usePluginStore: () => ({ executeFunction: mockExecuteFunction })
}));

vi.mock('../../elements/EditRow', () => ({
  default: ({ titleKey, onEdit, value, descriptionKey, validate }: any) => (
    <div>
      <span>{titleKey}</span>
      <span>{String(value)}</span>
      <span>{String(!!onEdit)}</span>
      <span>{String(!!descriptionKey)}</span>
      <span>{String(!!validate?.('12'))}</span>
    </div>
  )
}));

vi.mock('./SettingsSection', () => ({
  default: ({ children, title }: any) => <div><span>{title}</span>{children}</div>
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === apiConfigContextToken) return configValue;
      return actual.useContext(context);
    }
  };
});

import SecuritySection from './SecuritySection';

describe('SecuritySection', () => {
  beforeEach(() => {
    configValue = { config: { configuration: { auth: { allow_apikeys: true } } } };
    mockGet.mockReset();
    mockExecuteFunction.mockReset();
    mockExecuteFunction.mockReturnValue(<div>plugin-setting</div>);
  });

  it('renders password, apikeys, and plugin settings for non-oauth users', () => {
    mockGet.mockReturnValue('token');
    const removeApiKey = vi.fn();
    const addApiKey = vi.fn();
    render(
      <SecuritySection
        user={{ apikeys: [['KeyOne', ['R', 'W'], '2099-01-01'], ['Expired', [], '2000-01-01']], api_quota: 5 } as any}
        editPassword={vi.fn()}
        addApiKey={addApiKey}
        removeApiKey={removeApiKey}
        editQuota={vi.fn()}
      />
    );

    expect(screen.getByText('page.settings.security.table.password')).toBeInTheDocument();
    expect(screen.getByText('keyone (apikey.read, apikey.write)')).toBeInTheDocument();
    expect(screen.getByText('expired')).toBeInTheDocument();
    fireEvent.click(screen.getByText('keyone (apikey.read, apikey.write)'));
    expect(removeApiKey).toHaveBeenCalled();
    fireEvent.click(screen.getByText('add-icon'));
    expect(addApiKey).toHaveBeenCalled();
    expect(screen.getByText('plugin-setting')).toBeInTheDocument();
  });

  it('hides password rows for oauth tokens and shows none when no api keys exist', () => {
    mockGet.mockReturnValue('a.b.c');
    render(<SecuritySection user={{ apikeys: [], api_quota: 1 } as any} />);
    expect(screen.queryByText('page.settings.security.table.password')).not.toBeInTheDocument();
    expect(screen.getByText('none')).toBeInTheDocument();
  });
});
