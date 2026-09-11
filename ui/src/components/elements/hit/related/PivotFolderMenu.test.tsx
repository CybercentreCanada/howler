import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { Pivot } from 'models/entities/generated/Pivot';
import type { menuPathNode } from 'utils/pivotForest';
import PivotFolderMenu from './PivotFolderMenu';

vi.mock('@iconify/react', () => ({
  Icon: () => <span />
}));

vi.mock('components/elements/hit/ResolvePivotUrl', () => ({
  default: (pivot: Pivot) => `https://example.test/${pivot.value}`
}));

vi.mock('components/elements/hit/related/PivotLink', () => ({
  default: ({ pivot, resolvedUrl }: { pivot: Pivot; resolvedUrl: string }) =>
    pivot.format === 'link' ? (
      <a href={resolvedUrl} target="_blank" rel="noopener noreferrer">
        {pivot.label?.en}
      </a>
    ) : (
      <button type="button" onClick={event => event.stopPropagation()}>
        {pivot.label?.en}
      </button>
    )
}));

const dossier = { dossier_id: 'dossier-1' } as Dossier;
const mainPivot = { format: 'link', value: 'main', label: { en: 'Main', fr: 'Principal' } } as Pivot;
const nestedPivot = { format: 'link', value: 'nested', label: { en: 'Nested', fr: 'Imbrique' } } as Pivot;
const pluginPivot = { format: 'clue', value: 'plugin', label: { en: 'Plugin', fr: 'Extension' } } as Pivot;
const node: menuPathNode = {
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

  it('renders a pivot URL as a link that can be activated with the keyboard', async () => {
    const user = userEvent.setup();

    render(<PivotFolderMenu node={node} />);

    await user.click(screen.getByRole('button'));

    const link = await screen.findByRole('link', { name: 'Nested' });
    expect(link).toHaveAttribute('href', 'https://example.test/nested');
    expect(link).toHaveAttribute('target', '_blank');

    link.focus();
    await user.keyboard('{Enter}');

    expect(screen.queryByRole('menuitem')).not.toBeInTheDocument();
  });

  it('leaves plugin pivot activation under the plugin control', async () => {
    const user = userEvent.setup();
    const open = vi.spyOn(window, 'open').mockReturnValue(null);
    const pluginNode = {
      ...node,
      pivots: [node.pivots![0], { pivot: pluginPivot, dossier }]
    };

    render(<PivotFolderMenu node={pluginNode} />);

    await user.click(screen.getByRole('button'));
    await user.click(await screen.findByRole('button', { name: 'Plugin' }));

    expect(open).not.toHaveBeenCalled();
    expect(screen.getByRole('menuitem')).toBeInTheDocument();
  });
});
