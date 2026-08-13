import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { HitLayout } from './HitLayout';
import HitOutline from './HitOutline';

const addFilter = vi.fn();
const getMatchingTemplate = vi.fn((_hit, template) => Promise.resolve(template));

vi.mock('components/app/hooks/useMatchers', () => ({
  default: () => ({ getMatchingTemplate })
}));

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

vi.mock('utils/constants', () => ({
  PROVIDER_COLORS: { unknown: '#000000' },
  StorageKey: { TEMPLATE_FIELD_COUNT: 'template-field-count' }
}));

vi.mock('utils/utils', () => ({
  stringToColor: () => '#ffffff'
}));

describe('HitOutline', () => {
  it('renders supplied template fields and adds a filter for the selected value', async () => {
    const user = userEvent.setup();
    const hit = {
      event: { provider: 'endpoint' },
      howler: { id: 'hit-1', analytic: 'analytic-1', detection: 'hit-detection' },
      details: { values: ['first', 'second'] }
    } as any;
    const template = {
      keys: ['event.provider', 'details.values'],
      type: 'global',
      detection: 'template-detection'
    } as any;

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
});
