/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiConfigContextToken = vi.hoisted(() => ({ name: 'api-config-context' }));
const mockExecuteFunction = vi.hoisted(() => vi.fn());
const delayCancel = vi.hoisted(() => vi.fn());

let configValue: any = { config: { lookups: { roles: ['admin', 'member'] } } };

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return {
    ...actual,
    Add: () => <div>add</div>,
    Check: () => <div>check</div>,
    ChevronRight: () => <div>chevron</div>,
    Clear: () => <div>clear</div>
  };
});

vi.mock('@mui/material', () => ({
  Chip: ({ label, onClick, onDelete, icon }: any) => (
    <button onClick={onClick ?? onDelete}>
      {label}
      {icon}
    </button>
  ),
  CircularProgress: () => <div>progress</div>,
  Grid: ({ children }: any) => <div>{children}</div>,
  TableCell: ({ children }: any) => <div>{children}</div>,
  TableRow: ({ children, onClick }: any) => <div onClick={onClick}>{children}</div>,
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/app/providers/ApiConfigProvider', () => ({
  ApiConfigContext: apiConfigContextToken
}));

vi.mock('plugins/store', () => ({
  default: { plugins: ['demo'] }
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-pluggable', () => ({
  usePluginStore: () => ({ executeFunction: mockExecuteFunction })
}));

vi.mock('utils/utils', async importOriginal => {
  const actual = await importOriginal<typeof import('utils/utils')>();
  return {
    ...actual,
    delay: () => ({
      then: (cb: any) => {
        cb();
        return Promise.resolve();
      },
      cancel: delayCancel
    })
  };
});

vi.mock('../../elements/EditRow', () => ({
  default: ({ titleKey, value }: any) => <div>{`${titleKey}:${value}`}</div>
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

import ProfileSection from './ProfileSection';

describe('ProfileSection', () => {
  beforeEach(() => {
    configValue = { config: { lookups: { roles: ['admin', 'member'] } } };
    mockExecuteFunction.mockReset();
    mockExecuteFunction.mockReturnValue(<div>profile-plugin</div>);
    delayCancel.mockReset();
  });

  it('adds roles and opens group viewing when handlers are available', async () => {
    const addRole = vi.fn().mockResolvedValue(undefined);
    const viewGroups = vi.fn().mockResolvedValue(undefined);
    render(
      <ProfileSection
        user={{ username: 'alice', email: 'a@example.com', name: 'Alice', roles: ['member'] } as any}
        addRole={addRole}
        viewGroups={viewGroups}
      />
    );

    fireEvent.click(screen.getByText(/admin/));
    await waitFor(() => expect(addRole).toHaveBeenCalledWith('admin'));
    fireEvent.click(screen.getByText('page.settings.profile.table.groups'));
    await waitFor(() => expect(viewGroups).toHaveBeenCalled());
    expect(screen.getByText('profile-plugin')).toBeInTheDocument();
  });

  it('removes roles and shows check icon when removal is disabled', async () => {
    const removeRole = vi.fn().mockResolvedValue(undefined);
    const { rerender } = render(
      <ProfileSection user={{ username: 'alice', email: 'a@example.com', roles: ['admin'] } as any} removeRole={removeRole} />
    );

    fireEvent.click(screen.getByText(/admin/));
    await waitFor(() => expect(removeRole).toHaveBeenCalledWith('admin'));

    rerender(<ProfileSection user={{ username: 'alice', email: 'a@example.com', roles: ['admin'] } as any} />);
    expect(screen.getByText(/admin/)).toHaveTextContent('check');
  });
});
