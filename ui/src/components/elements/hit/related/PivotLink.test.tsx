import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { Hit } from 'models/entities/generated/Hit';
import type { Pivot } from 'models/entities/generated/Pivot';
import type { PropsWithChildren } from 'react';
import { BrowserRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PivotLink from './pivots/PivotLink';

const executeFunction = vi.hoisted(() => vi.fn());

vi.mock('react-pluggable', async importOriginal => ({
  ...(await importOriginal<typeof import('react-pluggable')>()),
  usePluginStore: () => ({ executeFunction })
}));

vi.mock('components/elements/display/handlebars/helpers', () => ({
  useHelpers: () => []
}));

vi.mock('components/elements/display/HowlerCard', () => ({
  default: ({ children }: PropsWithChildren) => <div>{children}</div>
}));

vi.mock('plugins/store', () => ({
  default: { pivotFormats: ['plugin'] }
}));

vi.mock('./RelatedIcon', () => ({ default: () => null }));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ i18n: { language: 'en' }, t: (key: string) => key })
}));

describe('PivotLink', () => {
  const resolvedUrl = 'https://example.com/alert';
  const dossier = {
    dossier_id: 'test-dossier',
    title: 'Test Dossier',
    owner: 'test-owner',
    query: 'howler.id:test-hit',
    leads: [{ content: 'Test lead description' }]
  } as Dossier;
  const hit = { howler: { id: 'test-hit' } } as Hit;

  beforeEach(() => {
    executeFunction.mockReset();
    executeFunction.mockReturnValue(<button>Plugin pivot</button>);
  });

  it.each(['link', 'plugin'])('shows the dossier and pivot descriptions for a %s pivot', async format => {
    const user = userEvent.setup();
    const pivot = {
      format,
      value: resolvedUrl,
      description: 'Pivot-specific description',
      label: { en: 'Link pivot', fr: 'Link pivot' },
      mappings: []
    } as Pivot;

    render(
      <BrowserRouter>
        <PivotLink pivot={pivot} hit={hit} dossier={dossier} />
      </BrowserRouter>
    );

    await user.hover(
      format === 'link'
        ? screen.getByRole('link', { name: 'Link pivot' })
        : screen.getByRole('button', { name: 'Plugin pivot' })
    );

    const tooltip = within(await screen.findByRole('tooltip'));
    const expectedUrl = format === 'link' ? resolvedUrl : '/dossier/test-dossier';
    expect(tooltip.getByText('Test Dossier')).toBeInTheDocument();
    expect(tooltip.getByText('test-owner')).toBeInTheDocument();
    expect(tooltip.getByText('pivot.description.header')).toBeInTheDocument();
    expect(tooltip.getByText('Pivot-specific description')).toBeInTheDocument();
    expect(tooltip.getByRole('link', { name: expectedUrl })).toHaveAttribute('href', expectedUrl);
    expect(tooltip.getByRole('link', { name: 'pivot.dossier.open' })).toHaveAttribute(
      'href',
      '/dossiers/test-dossier/edit?tab=leads&query=howler.id%3Atest-hit'
    );
  });

  it('shows the description inline for a menu-item link pivot', () => {
    const pivot = {
      format: 'link',
      value: resolvedUrl,
      description: '  Pivot-specific description  ',
      label: { en: 'Link pivot', fr: 'Link pivot' },
      mappings: []
    } as Pivot;

    render(
      <BrowserRouter>
        <PivotLink pivot={pivot} hit={hit} dossier={dossier} variant="menu-item" />
      </BrowserRouter>
    );

    const menuItem = within(screen.getByRole('menuitem'));
    expect(menuItem.getByText('Pivot-specific description')).toBeInTheDocument();
    expect(menuItem.getByText('Test Dossier • test-owner')).toBeInTheDocument();
    expect(menuItem.getByText(resolvedUrl)).toBeInTheDocument();
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });

  it.each([undefined, '', '   '])('omits the menu-item description when it is %j', description => {
    const pivot = {
      format: 'link',
      value: resolvedUrl,
      description,
      label: { en: 'Link pivot', fr: 'Link pivot' },
      mappings: []
    } as Pivot;

    render(
      <BrowserRouter>
        <PivotLink pivot={pivot} hit={hit} dossier={dossier} variant="menu-item" />
      </BrowserRouter>
    );

    const menuItem = screen.getByRole('menuitem');
    expect(within(menuItem).getByText('Test Dossier • test-owner')).toBeInTheDocument();
    expect(within(menuItem).getByText(resolvedUrl)).toBeInTheDocument();
    expect(menuItem.querySelectorAll('.MuiTypography-caption')).toHaveLength(2);
  });

  it('omits the description header when the pivot description is blank', async () => {
    const user = userEvent.setup();
    const pivot = {
      format: 'link',
      value: resolvedUrl,
      description: '   ',
      label: { en: 'Link pivot', fr: 'Link pivot' },
      mappings: []
    } as Pivot;

    render(
      <BrowserRouter>
        <PivotLink pivot={pivot} hit={hit} dossier={dossier} />
      </BrowserRouter>
    );

    await user.hover(screen.getByRole('link', { name: 'Link pivot' }));

    const tooltip = within(await screen.findByRole('tooltip'));
    expect(tooltip.queryByText('pivot.description.header')).not.toBeInTheDocument();
  });
});
