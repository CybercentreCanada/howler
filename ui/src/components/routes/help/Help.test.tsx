/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const mockExecuteFunction = vi.hoisted(() => vi.fn(() => <div key="plugin-help">plugin help</div>));

vi.mock('@tui/core', () => ({
  PageCenter: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/hooks/useMyPreferences', () => ({
  default: () => ({
    leftnav: {
      menus: [
        {
          id: 'help',
          items: [
            { id: 'help.main', i18nKey: 'help.main', route: '/help/main', icon: <span>skip</span> },
            { id: 'help.hit', i18nKey: 'help.hit', route: '/help/hit', icon: <span>hit</span> },
            { id: 'help.actions', i18nKey: 'help.actions', route: '/help/actions', icon: <span>action</span> },
            { id: 'help.advanced', i18nKey: 'help.advanced', route: '/help/advanced', icon: <span>advanced</span> },
            { id: 'help.cases', i18nKey: 'help.cases', route: '/help/cases', icon: <span>cases</span> },
            { id: 'help.dossiers', i18nKey: 'help.dossiers', route: '/help/dossiers', icon: <span>dossiers</span> }
          ]
        }
      ]
    }
  })
}));

vi.mock('components/hooks/useScrollRestoration', () => ({
  useScrollRestoration: vi.fn()
}));

vi.mock('plugins/store', () => ({
  default: {
    operations: ['triage'],
    plugins: ['sample-plugin']
  }
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: { defaultValue?: string }) => {
      const translations: Record<string, string> = {
        'help.advanced.overview.title': "Vue d'ensemble",
        'help.cases.overview.title': "Vue d'ensemble des cas",
        'help.dossiers.query.title': 'Requête correspondante'
      };
      return translations[key] ?? options?.defaultValue ?? key;
    }
  })
}));

vi.mock('react-pluggable', () => ({
  usePluginStore: () => ({ executeFunction: mockExecuteFunction })
}));

vi.mock('react-router', async () => {
  const { forwardRef } = await import('react');
  return {
    Link: forwardRef<HTMLAnchorElement, { to: string; children?: React.ReactNode; [key: string]: any }>(
      ({ to, children, ...props }, ref) => (
        <a ref={ref} href={to} {...props}>
          {children}
        </a>
      )
    )
  };
});

import HelpDashboard from './Help';

describe('HelpDashboard', () => {
  it('renders help cards, action tabs, and plugin help content', () => {
    render(<HelpDashboard />);

    expect(screen.getByText('page.help.title')).toBeInTheDocument();
    expect(screen.getByText('help.hit')).toBeInTheDocument();
    expect(screen.getByText('help.actions')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'triage' })).toHaveAttribute('href', '/help/actions?tab=triage');
    expect(screen.getByRole('link', { name: "Vue d'ensemble" })).toHaveAttribute('href', '/help/advanced?tab=overview');
    expect(screen.getByRole('link', { name: "Vue d'ensemble des cas" })).toHaveAttribute(
      'href',
      '/help/cases?tab=overview'
    );
    expect(screen.getByRole('link', { name: 'Requête correspondante' })).toHaveAttribute(
      'href',
      '/help/dossiers?tab=query'
    );
    expect(screen.getByText('plugin help')).toBeInTheDocument();
    expect(mockExecuteFunction).toHaveBeenCalledWith('sample-plugin.help');
  });
});
