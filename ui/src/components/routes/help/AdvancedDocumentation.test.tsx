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

  it.each([
    { language: 'en', heading: 'Explain' },
    { language: 'fr', heading: 'Expliquer' }
  ])('renders the query validation guide and JSON example in $language', async ({ language, heading }) => {
    mockLanguage.value = language;
    mockSearchParams.value = new URLSearchParams({ tab: 'lucene' });

    render(<AdvancedDocumentation />);

    expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument();
    expect(await screen.findByText('explanations')).toBeInTheDocument();
  });

  it.each([
    { language: 'en', exception: 'EQL is an exception:' },
    { language: 'fr', exception: 'EQL fait exception :' }
  ])('renders the EQL field-selection exception in $language', ({ language, exception }) => {
    mockLanguage.value = language;
    mockSearchParams.value = new URLSearchParams({ tab: 'results' });

    render(<AdvancedDocumentation />);

    expect(screen.getByText(exception, { selector: 'strong' })).toBeInTheDocument();
  });
});
