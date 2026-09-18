/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const mockUseMediaQuery = vi.hoisted(() => vi.fn(() => false));
const mockAppUser = vi.hoisted(() => ({ user: { is_admin: true } }));
const mockLocation = vi.hoisted(() => ({ hash: '#overview' }));

vi.mock('@mui/material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/material')>();
  return {
    ...actual,
    useMediaQuery: mockUseMediaQuery
  };
});

vi.mock('@tui/core', () => ({
  PageCenter: ({ children }: any) => <div>{children}</div>,
  useAppBar: () => ({ autoHide: false }),
  useAppLayout: () => ({ current: 'side' }),
  useAppUser: () => mockAppUser
}));

vi.mock('components/hooks/useScrollRestoration', () => ({
  useScrollRestoration: vi.fn()
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-router', () => ({
  useLocation: () => mockLocation
}));

vi.mock('./components/HelpTabs', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import SearchDocumentation from './SearchDocumentation';

const config = {
  indexes: {
    hit: {
      'howler.id': { indexed: true, type: 'keyword', stored: true, list: false, default: true },
      'howler.tags': { indexed: true, type: 'text', stored: false, list: true, default: false }
    },
    user: {
      uname: { indexed: true, type: 'keyword', stored: false, list: false, default: false }
    }
  }
} as any;

describe('SearchDocumentation', () => {
  it('returns nothing when indexes are unavailable', () => {
    const { container } = render(
      <ApiConfigContext.Provider value={{ config: {} } as any}>
        <SearchDocumentation />
      </ApiConfigContext.Provider>
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('renders the documented sections and indexed field tables when indexes are available', () => {
    render(
      <ApiConfigContext.Provider value={{ config } as any}>
        <SearchDocumentation />
      </ApiConfigContext.Provider>
    );

    expect(screen.getByText('title')).toBeInTheDocument();
    expect(screen.getAllByText('overview').length).toBeGreaterThan(0);
    expect(screen.getAllByText('fields.idx_hit').length).toBeGreaterThan(0);
    expect(screen.getAllByText('fields.idx_user').length).toBeGreaterThan(0);
    expect(screen.getByText('howler.id')).toBeInTheDocument();
    expect(screen.getByText('howler.tags')).toBeInTheDocument();
    expect(screen.getByText('uname')).toBeInTheDocument();
    expect(screen.getAllByText('wildcard').length).toBeGreaterThan(0);
    expect(screen.getAllByText('regex').length).toBeGreaterThan(0);
    expect(screen.getAllByText('ranges').length).toBeGreaterThan(0);
    expect(screen.getAllByText('reserved').length).toBeGreaterThan(0);
  });
});
