/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockUseMediaQuery = vi.hoisted(() => vi.fn(() => false));
const mockSetSearchParams = vi.hoisted(() => vi.fn());
const mockSearchParams = vi.hoisted(() => ({ value: new URLSearchParams() }));
const mockLanguage = vi.hoisted(() => ({ value: 'en' }));

vi.mock('@mui/material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/material')>();
  return {
    ...actual,
    useMediaQuery: mockUseMediaQuery
  };
});

vi.mock('@tui/core', () => ({
  PageCenter: ({ children }: any) => <div>{children}</div>,
  useAppTheme: () => ({ isDark: false })
}));

vi.mock('mermaid', () => ({
  default: {
    initialize: vi.fn(),
    run: vi.fn()
  }
}));

vi.mock('components/elements/display/Notebook', () => ({
  Notebook: () => null
}));

vi.mock('components/hooks/useScrollRestoration', () => ({
  useScrollRestoration: vi.fn()
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    i18n: { language: mockLanguage.value },
    t: (key: string) =>
      key === 'route.advanced.query.lucene' ? (mockLanguage.value === 'fr' ? 'Requête Lucene' : 'Lucene Query') : key
  })
}));

vi.mock('react-router', () => ({
  Link: ({ children, to }: any) => <a href={to}>{children}</a>,
  useSearchParams: () => [mockSearchParams.value, mockSetSearchParams]
}));

vi.mock('./components/HelpTabs', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

import AdvancedDocumentation from './AdvancedDocumentation';

describe('AdvancedDocumentation', () => {
  beforeEach(() => {
    mockLanguage.value = 'en';
    mockSearchParams.value = new URLSearchParams({ tab: 'languages', keep: 'value' });
    mockSetSearchParams.mockClear();
  });

  it('renders the query-selected tab and updates the query string when navigating', async () => {
    const user = userEvent.setup();

    render(<AdvancedDocumentation />);

    expect(screen.getByRole('heading', { name: 'Choose a query language' })).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'help.advanced.lucene.title' }));

    expect(mockSetSearchParams).toHaveBeenCalledTimes(1);
    const nextParams = mockSetSearchParams.mock.calls[0][0] as URLSearchParams;
    expect(nextParams.get('tab')).toBe('lucene');
    expect(nextParams.get('keep')).toBe('value');
  });

  it('renders localized Markdown and translated preview components', () => {
    mockLanguage.value = 'fr';

    render(<AdvancedDocumentation />);

    expect(screen.getByRole('heading', { name: 'Choisir un langage de requête' })).toBeInTheDocument();
    const previewLabel = screen.getByText('Requête Lucene', { selector: '.MuiChip-label' });
    expect(previewLabel).toBeInTheDocument();
    expect(previewLabel.closest('p')).toBeNull();
  });
});
