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
    t: (key: string) => {
      const labels: Record<string, { en: string; fr: string }> = {
        'modal.cases.add_to_case': { en: 'Add to Case', fr: 'Ajouter au cas' },
        'page.cases.sidebar.add_event': { en: 'Add event', fr: 'Ajouter un événement' }
      };

      return labels[key]?.[mockLanguage.value as 'en' | 'fr'] ?? key;
    }
  })
}));

vi.mock('react-router', () => ({
  Link: ({ children, to }: any) => <a href={to}>{children}</a>,
  useSearchParams: () => [mockSearchParams.value, mockSetSearchParams]
}));

vi.mock('./components/HelpTabs', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

import CaseDocumentation from './CaseDocumentation';

describe('CaseDocumentation', () => {
  beforeEach(() => {
    mockLanguage.value = 'en';
    mockSearchParams.value = new URLSearchParams({ tab: 'summary', keep: 'value' });
    mockSetSearchParams.mockClear();
  });

  it('renders the query-selected tab and updates the query string when navigating', async () => {
    const user = userEvent.setup();

    render(<CaseDocumentation />);

    expect(screen.getByRole('heading', { name: 'Case summary' })).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'help.cases.rules.title' }));

    expect(mockSetSearchParams).toHaveBeenCalledTimes(1);
    const nextParams = mockSetSearchParams.mock.calls[0][0] as URLSearchParams;
    expect(nextParams.get('tab')).toBe('rules');
    expect(nextParams.get('keep')).toBe('value');
  });

  it('renders localized Markdown and translated preview components', () => {
    mockLanguage.value = 'fr';
    mockSearchParams.value = new URLSearchParams({ tab: 'records' });

    render(<CaseDocumentation />);

    expect(screen.getByRole('heading', { name: 'Ajouter des enregistrements aux cas' })).toBeInTheDocument();
    const previewLabel = screen.getByText('Ajouter au cas', { selector: '.MuiTypography-body2' });
    expect(previewLabel).toBeInTheDocument();
    expect(previewLabel.parentElement?.closest('p')).toBeNull();
  });

  it.each([
    { language: 'en', label: 'Add event', link: 'Adding records to cases' },
    { language: 'fr', label: 'Ajouter un événement', link: 'Ajouter des enregistrements aux cas' }
  ])('renders the event control and records guide link in $language', ({ language, label, link }) => {
    mockLanguage.value = language;
    mockSearchParams.value = new URLSearchParams({ tab: 'sidebar' });

    render(<CaseDocumentation />);

    expect(screen.getByText(label, { selector: '.MuiChip-label' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: link })).toHaveAttribute('href', '/help/cases?tab=records');
  });

  it.each([
    { language: 'en', heading: 'Backfill historical matches', control: 'Submit to correlation' },
    { language: 'fr', heading: 'Rattraper les correspondances historiques', control: 'Soumettre à la corrélation' }
  ])('renders the historical backfill guide in $language', ({ language, heading, control }) => {
    mockLanguage.value = language;
    mockSearchParams.value = new URLSearchParams({ tab: 'rules' });

    render(<CaseDocumentation />);

    expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument();
    expect(screen.getByText(control, { selector: 'strong' })).toBeInTheDocument();
  });
});
