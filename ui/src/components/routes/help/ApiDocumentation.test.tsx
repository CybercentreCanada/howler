/// <reference types="vitest" />
import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const mockUseMediaQuery = vi.hoisted(() => vi.fn(() => false));
const mockDispatchApi = vi.hoisted(() => vi.fn((promise: any) => Promise.resolve(promise)));
const mockHelpGet = vi.hoisted(() => vi.fn());

vi.mock('@mui/material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/material')>();
  return {
    ...actual,
    useMediaQuery: mockUseMediaQuery
  };
});

vi.mock('@tui/core', () => ({
  PageCenter: ({ children }: any) => <div>{children}</div>,
  useAppUser: () => ({ user: { roles: ['admin'] } })
}));

vi.mock('api', () => ({
  default: {
    help: {
      get: mockHelpGet
    }
  }
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('components/hooks/useScrollRestoration', () => ({
  useScrollRestoration: vi.fn()
}));

vi.mock('components/elements/display/Markdown', () => ({
  default: ({ md }: { md: string }) => <div>{md}</div>
}));

vi.mock('react-i18next', () => ({
  Trans: ({ i18nKey }: { i18nKey: string }) => <span>{i18nKey}</span>,
  useTranslation: () => ({ t: (key: string) => key })
}));

import ApiDocumentation from './ApiDocumentation';

describe('ApiDocumentation', () => {
  it('shows a loading state until API documentation arrives', () => {
    mockHelpGet.mockReturnValue({ apis: [], blueprints: {} });
    mockDispatchApi.mockImplementation(() => new Promise(() => {}));

    render(<ApiDocumentation />);

    expect(screen.getByText('loading')).toBeInTheDocument();
  });

  it('renders categories and endpoint details once the API documentation is loaded', async () => {
    mockHelpGet.mockReturnValue({
      blueprints: { admin: 'Admin APIs' },
      apis: [
        {
          id: '1',
          name: 'Users',
          path: '/api/v1/user',
          complete: true,
          protected: true,
          methods: ['GET', 'POST'],
          ui_only: true,
          required_type: ['admin'],
          required_priv: ['R', 'W'],
          description: 'Data Block:\nvalue\nResult Example:\nresult'
        }
      ]
    });
    mockDispatchApi.mockImplementation((promise: any) => Promise.resolve(promise));

    render(<ApiDocumentation />);

    await waitFor(() => expect(screen.getByText('page.documentation.categories')).toBeInTheDocument());
    expect(screen.getAllByText('admin').length).toBeGreaterThan(0);
    expect(screen.getByText('Admin APIs')).toBeInTheDocument();
    expect(screen.getByText('Users')).toBeInTheDocument();
    expect(screen.getByText('/api/v1/user')).toBeInTheDocument();
    expect(screen.getByText('Stable')).toBeInTheDocument();
    expect(screen.getByText('Protected')).toBeInTheDocument();
    expect(screen.getByText('UI Only')).toBeInTheDocument();
    expect(screen.getByText('apikey.read')).toBeInTheDocument();
    expect(screen.getByText('apikey.write')).toBeInTheDocument();
    expect(screen.getByText(/Data Block:/)).toBeInTheDocument();
  });
});
