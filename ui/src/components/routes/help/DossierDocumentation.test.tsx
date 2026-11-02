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
      key === 'route.dossiers.manager.tabs.leads' ? (mockLanguage.value === 'fr' ? 'Pistes' : 'Leads') : key
  })
}));

vi.mock('react-router', () => ({
  Link: ({ children, to }: any) => <a href={to}>{children}</a>,
  useSearchParams: () => [mockSearchParams.value, mockSetSearchParams]
}));

vi.mock('./components/HelpTabs', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

vi.mock('../hits/search/RecordQuery', () => ({
  default: () => <div id="record-query-preview" />
}));

import DossierDocumentation from './DossierDocumentation';

describe('DossierDocumentation', () => {
  beforeEach(() => {
    mockLanguage.value = 'en';
    mockSearchParams.value = new URLSearchParams({ tab: 'usage', keep: 'value' });
    mockSetSearchParams.mockClear();
  });

  it('renders the query-selected tab and updates the query string when navigating', async () => {
    const user = userEvent.setup();

    render(<DossierDocumentation />);

    expect(screen.getByRole('heading', { name: 'Manage and use dossiers' })).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'help.dossiers.query.title' }));

    expect(mockSetSearchParams).toHaveBeenCalledTimes(1);
    const nextParams = mockSetSearchParams.mock.calls[0][0] as URLSearchParams;
    expect(nextParams.get('tab')).toBe('query');
    expect(nextParams.get('keep')).toBe('value');
  });

  it('renders localized Markdown and translated preview components', () => {
    mockLanguage.value = 'fr';
    mockSearchParams.value = new URLSearchParams({ tab: 'overview' });

    render(<DossierDocumentation />);

    expect(screen.getByRole('heading', { name: "Vue d'ensemble des dossiers" })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: "Guide d'investigation" })).toBeInTheDocument();
    expect(screen.getByRole('group')).toBeInTheDocument();
  });

  it('uses the dossier query control from the search route', () => {
    mockSearchParams.value = new URLSearchParams({ tab: 'query' });

    render(<DossierDocumentation />);

    expect(screen.getByRole('heading', { name: 'Define the matching query' })).toBeInTheDocument();
    expect(document.getElementById('record-query-preview')).toBeInTheDocument();
  });

  it.each([
    { language: 'en', heading: 'Organize pivot groups' },
    { language: 'fr', heading: 'Organiser les groupes de pivots' }
  ])('renders the pivot grouping guide in $language', ({ language, heading }) => {
    mockLanguage.value = language;
    mockSearchParams.value = new URLSearchParams({ tab: 'pivots' });

    render(<DossierDocumentation />);

    expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument();
    expect(screen.getByText('SIEM/Hosts', { selector: 'code' })).toBeInTheDocument();
  });
});
