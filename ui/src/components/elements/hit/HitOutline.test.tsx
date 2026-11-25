import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { Hit } from 'models/entities/generated/Hit';
import type { Template } from 'models/entities/generated/Template';
import type { WithMetadata } from 'models/WithMetadata';
import { BrowserRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import { HitLayout } from './HitLayout';
import HitOutline from './HitOutline';

const addFilter = vi.fn();
vi.mock('components/app/providers/RecordProvider', () => ({ RecordContext: {} }));

vi.mock('components/app/providers/ApiConfigProvider', async () => {
  const { createContext } = await import('react');

  return {
    ApiConfigContext: createContext({ config: { indexes: { hit: {} } } })
  };
});

vi.mock('components/app/providers/ParameterProvider', () => ({
  ParameterContext: {}
}));

vi.mock('components/hooks/useMyLocalStorage', () => ({
  useMyLocalStorageItem: () => [null]
}));

vi.mock('components/elements/PluginTypography', () => ({
  default: ({ children }: { children: string }) => <span>{children}</span>
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('use-context-selector', () => ({
  useContextSelector: (_context: unknown, selector: (context: { addFilter: typeof addFilter }) => unknown) =>
    selector({ addFilter })
}));

vi.mock('utils/utils', () => ({
  getProviderColor: (_provider: string | undefined) => '#000000',
  notNil: (value: unknown) => value !== null && value !== undefined
}));

vi.mock('utils/constants', () => ({
  StorageKey: { TEMPLATE_FIELD_COUNT: 'template-field-count' }
}));

describe('HitOutline', () => {
  const record: Hit = {
    __index: 'hit',
    timestamp: '2026-01-01T00:00:00Z',
    howler: { id: 'hit-1', analytic: 'analytic-1', assignment: 'unassigned', hash: '1', detection: 'hit-detection' }
  };

  it('renders supplied template fields and adds a filter for the selected value', async () => {
    const user = userEvent.setup();
    const hit = {
      ...record,
      event: { provider: 'endpoint' },
      details: { values: ['first', 'second'] }
    };
    const template: Template = {
      keys: ['event.provider', 'details.values'],
      type: 'global',
      detection: 'template-detection'
    };

    render(
      <BrowserRouter>
        <HitOutline hit={hit} layout={HitLayout.NORMAL} template={template} />
      </BrowserRouter>
    );

    expect(await screen.findByText('event.provider:')).toBeInTheDocument();
    expect(screen.getByText('endpoint')).toBeInTheDocument();
    expect(screen.getByText('details.values:')).toBeInTheDocument();
    expect(screen.getByText('first, second')).toBeInTheDocument();
    expect(screen.getByRole('link')).toHaveAttribute(
      'href',
      '/templates/view?analytic=analytic-1&type=global&detection=template-detection'
    );

    await user.click(screen.getAllByLabelText('hit.outline.add_filter')[0]);

    expect(addFilter).toHaveBeenCalledWith('event.provider:"endpoint"');
  });

  it('links a readonly metadata match to its built-in template and shows the lock', async () => {
    const hit: WithMetadata<Hit> = {
      ...record,
      __template: { type: 'readonly', detection: 'builtin-detection', keys: ['howler.id'] }
    };
    render(
      <BrowserRouter>
        <HitOutline hit={hit} layout={HitLayout.NORMAL} />
      </BrowserRouter>
    );

    const link = await screen.findByRole('link', { name: 'route.templates.builtin' });
    expect(link).toHaveAttribute(
      'href',
      '/templates/view?analytic=analytic-1&type=readonly&detection=builtin-detection'
    );
    expect(link.querySelector('[data-testid="LockIcon"]')).toBeInTheDocument();
  });
});
