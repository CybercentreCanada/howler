import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { MenuPathNode } from 'components/routes/dossiers/utils';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { Pivot } from 'models/entities/generated/Pivot';
import PivotFolderMenu from './PivotFolderMenu';

vi.mock('@iconify/react', () => ({
  Icon: () => <span />
}));

vi.mock('components/elements/hit/related/pivots/PivotLink', () => ({
  default: ({ pivot, variant }: { pivot: Pivot; variant?: 'card' | 'menu-item' }) =>
    pivot.format === 'link' ? (
      <a href={`https://example.test/${pivot.value}`} role={variant === 'menu-item' ? 'menuitem' : undefined}>
        {pivot.label?.en}
      </a>
    ) : (
      <button
        type="button"
        role={variant === 'menu-item' ? 'menuitem' : undefined}
        onClick={event => event.stopPropagation()}
      >
        {pivot.label?.en}
      </button>
    )
}));

const dossier = { dossier_id: 'dossier-1' } as Dossier;
const mainPivot = { format: 'link', value: 'main', label: { en: 'Main', fr: 'Principal' } } as Pivot;
const nestedPivot = { format: 'link', value: 'nested', label: { en: 'Nested', fr: 'Imbrique' } } as Pivot;
const pluginPivot = { format: 'clue', value: 'plugin', label: { en: 'Plugin', fr: 'Extension' } } as Pivot;
const node: MenuPathNode = {
  path: 'example',
  pivots: [
    { pivot: mainPivot, dossier },
    { pivot: nestedPivot, dossier }
  ],
  children: []
};

describe('PivotFolderMenu', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('opens a grouped pivot menu with the keyboard', async () => {
    const user = userEvent.setup();

    render(<PivotFolderMenu node={node} />);

    const trigger = screen.getByRole('button', { name: /example/i });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');

    await user.tab();
    expect(trigger).toHaveFocus();
    await user.keyboard('{Enter}');

    const link = await screen.findByRole('menuitem', { name: 'Nested' });
    expect(link).toHaveAttribute('href', 'https://example.test/nested');
    expect(trigger).toHaveAttribute('aria-expanded', 'true');

    await user.keyboard('{Escape}');
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    expect(trigger).toHaveFocus();
  });

  it('leaves plugin pivot activation under the plugin control', async () => {
    const user = userEvent.setup();
    const open = vi.spyOn(window, 'open').mockReturnValue(null);
    const pluginNode = {
      ...node,
      pivots: [node.pivots![0], { pivot: pluginPivot, dossier }]
    };

    render(<PivotFolderMenu node={pluginNode} />);

    await user.click(screen.getByRole('button', { name: /example/i }));
    await user.click(await screen.findByRole('menuitem', { name: 'Plugin' }));

    expect(open).not.toHaveBeenCalled();
    expect(screen.getByRole('menuitem', { name: 'Plugin' })).toBeInTheDocument();
  });
});
