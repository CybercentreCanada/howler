/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

const mockUseMediaQuery = vi.hoisted(() => vi.fn(() => false));
const mockSetSearchParams = vi.hoisted(() => vi.fn());
const searchParams = new URLSearchParams({ tab: 'schema' });

vi.mock('@mui/material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/material')>();
  return {
    ...actual,
    useMediaQuery: mockUseMediaQuery
  };
});

vi.mock('@tui/core', () => ({
  PageCenter: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/hooks/useScrollRestoration', () => ({
  useScrollRestoration: vi.fn()
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-router', () => ({
  useSearchParams: () => [searchParams, mockSetSearchParams]
}));

vi.mock('./components/HelpTabs', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

vi.mock('./HitBannerDocumentation', () => ({
  default: () => <div>banner doc</div>
}));

vi.mock('./HitLabelsDocumentation', () => ({
  default: () => <div>labels doc</div>
}));

vi.mock('./HitLinksDocumentation', () => ({
  default: () => <div>links doc</div>
}));

vi.mock('./HitSchemaDocumentation', () => ({
  default: () => <div>schema doc</div>
}));

import HitDocumentation from './HitDocumentation';

describe('HitDocumentation', () => {
  it('renders the selected hit doc tab and updates the query string on tab changes', async () => {
    const user = userEvent.setup();

    render(<HitDocumentation />);

    expect(screen.getByText('schema doc')).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'help.hit.links.title' }));

    expect(screen.getByText('links doc')).toBeInTheDocument();
    expect(mockSetSearchParams).toHaveBeenCalled();
  });
});
