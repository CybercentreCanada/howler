import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { Hit } from 'models/entities/generated/Hit';
import type { Pivot } from 'models/entities/generated/Pivot';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PivotLink from './PivotLink';

const executeFunction = vi.hoisted(() => vi.fn());

vi.mock('@iconify/react', () => ({
  Icon: ({ icon }: { icon: string }) => <span id="icon" data-icon={icon} />
}));

vi.mock('components/elements/display/handlebars/helpers', () => ({
  useHelpers: () => [
    {
      keyword: 'upper',
      callback: (...args: unknown[]) => String(args[0]).toUpperCase()
    }
  ]
}));

vi.mock('components/elements/display/HowlerCard', () => ({
  default: ({ children }: { children: ReactNode }) => <div id="howler-card">{children}</div>
}));

vi.mock('components/elements/hit/PivotTooltip', () => ({
  default: () => <span data-testid="pivot-tooltip" />
}));

vi.mock('components/elements/hit/related/RelatedLink', () => ({
  default: ({
    title,
    href,
    target,
    rel,
    dense,
    secondary,
    action
  }: {
    title?: string;
    href?: string;
    target?: string;
    rel?: string;
    dense?: boolean;
    secondary?: ReactNode;
    action?: ReactNode;
  }) => (
    <div id="related-link" data-dense={String(dense)}>
      <a href={href} target={target} rel={rel}>
        {title}
      </a>
      {secondary}
      {action}
    </div>
  )
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    i18n: { language: 'en' },
    t: (key: string) => key
  })
}));

vi.mock('react-pluggable', () => ({
  usePluginStore: () => ({ executeFunction })
}));

const hit = {
  __index: 'hit',
  timestamp: '2026-01-01T00:00:00Z',
  howler: {},
  event: { domain: ['example.test'] },
  user: { name: 'alice' }
} as unknown as Hit;

const dossier = {
  dossier_id: 'dossier-1',
  title: 'Example dossier',
  owner: 'analyst',
  query: 'foo bar'
} as Dossier;

const linkPivot = {
  format: 'link',
  label: { en: 'Open result' },
  value: 'https://example.test/{{domain}}/{{token}}/{{upper user}}',
  mappings: [
    { key: 'domain', field: 'event.domain' },
    { key: 'token', field: 'custom', custom_value: 'fixed-token' },
    { key: 'user', field: 'user.name' }
  ]
} as Pivot;

const renderPivotLink = (pivot: Pivot, options: { compact?: boolean; dense?: boolean } = {}) =>
  render(
    <MemoryRouter>
      <PivotLink pivot={pivot} hit={hit} dossier={dossier} resolvedUrl="https://example.test/resolved" {...options} />
    </MemoryRouter>
  );

describe('PivotLink', () => {
  beforeEach(() => {
    executeFunction.mockReset();
    executeFunction.mockReturnValue(null);
  });

  it('resolves mapped hit values, custom values, and helpers in a link pivot', () => {
    renderPivotLink(linkPivot, { compact: true });

    const link = screen.getByRole('link', { name: 'Open result' });
    expect(link).toHaveAttribute('href', 'https://example.test/example.test/fixed-token/ALICE');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    expect(screen.getByTestId('related-link')).toHaveAttribute('data-dense', 'false');
    expect(executeFunction).not.toHaveBeenCalled();
  });

  it('renders dossier details and an edit action for dense link pivots', () => {
    renderPivotLink(linkPivot, { dense: true });

    expect(screen.getByTestId('related-link')).toHaveAttribute('data-dense', 'true');
    expect(screen.getByText('Example dossier • analyst')).toBeInTheDocument();
    expect(screen.getByText('https://example.test/example.test/fixed-token/ALICE')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'pivot.dossier.open' })).toHaveAttribute(
      'href',
      '/dossiers/dossier-1/edit?tab=leads&query=foo%20bar'
    );
  });

  it('renders a plugin-provided pivot implementation', () => {
    const pluginPivot = <button type="button">Plugin pivot</button>;
    executeFunction.mockReturnValue(pluginPivot);
    const pivot = { format: 'clue', value: 'plugin-value' } as Pivot;

    renderPivotLink(pivot, { compact: true });

    expect(screen.getByRole('button', { name: 'Plugin pivot' })).toBeInTheDocument();
    expect(executeFunction).toHaveBeenCalledWith('pivot.clue', { pivot, hit, compact: true });
    expect(screen.queryByTestId('related-link')).not.toBeInTheDocument();
  });

  it('renders an error indicator when no pivot implementation is available', () => {
    const pivot = { format: 'unsupported', value: 'unsupported-value' } as Pivot;

    renderPivotLink(pivot);

    expect(screen.getByTestId('howler-card')).toBeInTheDocument();
    expect(document.querySelector('[data-testid="ErrorOutlineIcon"]')).toBeInTheDocument();
    expect(screen.queryByTestId('related-link')).not.toBeInTheDocument();
    expect(executeFunction).toHaveBeenCalledWith('pivot.unsupported', { pivot, hit, compact: false });
  });
});
