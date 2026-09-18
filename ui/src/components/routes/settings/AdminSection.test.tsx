/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const mockExecuteFunction = vi.hoisted(() => vi.fn());

vi.mock('plugins/store', () => ({
  default: { plugins: ['demo'] }
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-pluggable', () => ({
  usePluginStore: () => ({ executeFunction: mockExecuteFunction })
}));

vi.mock('./SettingsSection', () => ({
  default: ({ children, title }: any) => <div><span>{title}</span>{children}</div>
}));

import AdminSection from './AdminSection';

describe('AdminSection', () => {
  it('renders plugin-provided admin settings', () => {
    mockExecuteFunction.mockReturnValue(<div>admin-plugin</div>);
    render(<AdminSection />);
    expect(screen.getByText('page.settings.admin.title')).toBeInTheDocument();
    expect(screen.getByText('admin-plugin')).toBeInTheDocument();
  });
});
