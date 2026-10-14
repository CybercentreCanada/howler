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
  useAppTheme: () => ({ isDark: false }),
  useAppUser: () => ({ user: { username: 'documentation-analyst' } })
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

vi.mock('components/elements/UserList', () => ({
  default: ({ userIds }: any) => <div>{userIds.join(',')}</div>
}));

vi.mock('components/elements/event/EventCard', () => ({
  default: ({ event }: any) => <div>{event.message}</div>
}));

vi.mock('../cases/detail/aggregates/CaseAggregate', () => ({
  default: ({ subtitle }: any) => <div>{subtitle}</div>
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
  useLocation: () => ({ pathname: '/cases/example-case', search: '' }),
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
    const previewLabel = screen.getByRole('heading', { name: 'Ajouter au cas' });
    expect(previewLabel).toBeInTheDocument();
  });

  it.each([
    { language: 'en', label: 'Add event', link: 'Adding records to cases' },
    { language: 'fr', label: 'Ajouter un événement', link: 'Ajouter des enregistrements aux cas' }
  ])('renders the event control and records guide link in $language', ({ language, label, link }) => {
    mockLanguage.value = language;
    mockSearchParams.value = new URLSearchParams({ tab: 'sidebar' });

    render(<CaseDocumentation />);

    expect(screen.getByRole('button', { name: label })).toBeInTheDocument();
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

  it.each([
    { tab: 'folders', example: 'Investigation' },
    { tab: 'investigation', example: 'page.cases.search' },
    { tab: 'rules', example: 'alerts/{{howler.analytic}}' }
  ])('renders the actual $tab example control', ({ tab, example }) => {
    mockSearchParams.value = new URLSearchParams({ tab });

    render(<CaseDocumentation />);

    expect(screen.getAllByText(example).length).toBeGreaterThan(0);
  });

  it('renders the actual item-type selector in the items guide', () => {
    mockSearchParams.value = new URLSearchParams({ tab: 'items' });

    render(<CaseDocumentation />);

    expect(screen.getByRole('combobox', { name: 'modal.cases.add_item.type' })).toBeInTheDocument();
  });

  it('shows the dashboard aggregate cards and timeline in the summary guide', () => {
    mockSearchParams.value = new URLSearchParams({ tab: 'summary' });

    render(<CaseDocumentation />);

    expect(screen.getByText('page.cases.dashboard.threat')).toBeInTheDocument();
    expect(screen.getByText('page.cases.dashboard.target')).toBeInTheDocument();
    expect(screen.getByText('page.cases.dashboard.indicators')).toBeInTheDocument();
    expect(screen.getByText('page.cases.dashboard.duration')).toBeInTheDocument();
    expect(screen.getByText('Manual evidence from VPN investigation')).toBeInTheDocument();
  });
});
