/// <reference types="vitest" />
import { createTheme, ThemeProvider } from '@mui/material';
import { render, screen } from '@testing-library/react';
import type { PropsWithChildren } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockUseMediaQuery = vi.hoisted(() => vi.fn(() => false));
const mockAppUser = vi.hoisted(() => ({ user: { is_admin: true } }));
const mockLocation = vi.hoisted(() => ({ hash: '#overview' }));
const mockAppBar = vi.hoisted(() => ({ autoHide: false }));
const mockAppLayout = vi.hoisted(() => ({ current: 'side' }));

vi.mock('@mui/material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/material')>();
  return {
    ...actual,
    useMediaQuery: mockUseMediaQuery
  };
});

vi.mock('@tui/core', () => ({
  PageCenter: ({ children, className }: PropsWithChildren<{ className?: string }>) => (
    <div className={className}>{children}</div>
  ),
  useAppBar: () => mockAppBar,
  useAppLayout: () => mockAppLayout,
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

const documentationWithSpacing = (spacing: number) => (
  <ThemeProvider theme={createTheme({ spacing })}>
    <ApiConfigContext.Provider value={{ config } as any}>
      <SearchDocumentation />
    </ApiConfigContext.Provider>
  </ThemeProvider>
);

describe('SearchDocumentation', () => {
  beforeEach(() => {
    mockAppBar.autoHide = false;
    mockAppLayout.current = 'side';
  });

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

  it.each([
    { density: 'default', spacing: 8 },
    { density: 'compact', spacing: 6 },
    { density: 'dense', spacing: 4 }
  ])('keeps section spacing positive at $density density', ({ spacing }) => {
    const { container } = render(documentationWithSpacing(spacing));
    const paragraphs = container.querySelectorAll('.paragraph');

    expect(paragraphs.length).toBeGreaterThan(0);
    paragraphs.forEach(paragraph => {
      const spacer = paragraph.querySelector('.spacer') as HTMLDivElement;

      expect(paragraph).toHaveStyle({ marginTop: `${-12 * spacing}px` });
      expect(spacer).toHaveStyle({ height: `${14 * spacing}px` });
      expect(parseFloat(getComputedStyle(paragraph).marginTop) + parseFloat(getComputedStyle(spacer).height)).toBe(
        2 * spacing
      );
    });
  });

  it('updates section offsets when density changes without remounting', () => {
    const { container, rerender } = render(documentationWithSpacing(8));
    const paragraph = container.querySelector('#overview');

    expect(paragraph).toHaveStyle({ marginTop: '-96px' });

    rerender(documentationWithSpacing(6));
    expect(paragraph).toHaveStyle({ marginTop: '-72px' });

    rerender(documentationWithSpacing(4));
    expect(paragraph).toHaveStyle({ marginTop: '-48px' });
  });

  it.each([
    { layout: 'side', marginTop: '0px' },
    { layout: 'top', marginTop: '-48px' }
  ])('preserves auto-hide offsets in the $layout layout at dense density', ({ layout, marginTop }) => {
    mockAppBar.autoHide = true;
    mockAppLayout.current = layout;
    const { container } = render(documentationWithSpacing(4));
    const paragraph = container.querySelector('#overview') as HTMLDivElement;

    expect(paragraph).toHaveStyle({ marginTop });
    expect(paragraph.classList.contains('autoHide')).toBe(layout === 'side');
  });
});
