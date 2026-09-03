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
  default: ({ pivot }: { pivot: Pivot }) => <span>{pivot.label?.en}</span>
}));

const dossier = { dossier_id: 'dossier-1' } as Dossier;
const mainPivot = { format: 'link', value: 'main', label: { en: 'Main', fr: 'Principal' } } as Pivot;
const nestedPivot = { format: 'link', value: 'nested', label: { en: 'Nested', fr: 'Imbrique' } } as Pivot;
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

  it.each([
    ['Enter', '{Enter}'],
    ['Space', ' ']
  ])('opens a pivot when its menu item is activated with %s', async (_key, input) => {
    const user = userEvent.setup();
    const open = vi.spyOn(window, 'open').mockReturnValue(null);

    render(<PivotFolderMenu node={node} />);

    await user.click(screen.getByRole('button'));

    const menuItem = await screen.findByRole('menuitem');
    menuItem.focus();
    await user.keyboard(input);

    expect(open).toHaveBeenCalledWith('https://example.test/nested', '_blank', 'noopener,noreferrer');
  });
});
