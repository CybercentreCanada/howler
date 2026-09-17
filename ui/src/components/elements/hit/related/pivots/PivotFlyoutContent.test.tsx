import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { MenuPathNode } from 'components/routes/dossiers/utils';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { Pivot } from 'models/entities/generated/Pivot';
import { describe, expect, it, vi } from 'vitest';
import PivotFlyoutContent from './PivotFlyoutContent';

vi.mock('components/elements/hit/related/pivots/PivotLink', () => ({
  default: ({ pivot, onNavigate }: { pivot: Pivot; onNavigate?: () => void }) => (
    <button type="button" role="menuitem" onClick={onNavigate}>
      {pivot.label?.en}
    </button>
  )
}));

const dossier = { dossier_id: 'dossier-1' } as Dossier;
const pivot = (value: string, label: string): Pivot => ({
  format: 'link',
  value,
  label: { en: label, fr: label }
});

describe('PivotFlyoutContent', () => {
  it('opens and closes a nested group with keyboard navigation', async () => {
    const user = userEvent.setup();
    const groups: MenuPathNode[] = [
      {
        path: 'network',
        pivots: [{ pivot: pivot('dns', 'DNS'), dossier }],
        children: []
      }
    ];

    render(<PivotFlyoutContent pivots={[]} groups={groups} />);

    const group = screen.getByRole('menuitem', { name: 'network' });
    await user.click(group);

    expect(group).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('menuitem', { name: 'DNS' })).toBeInTheDocument();

    await user.keyboard('{ArrowLeft}');

    expect(group).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('menuitem', { name: 'DNS' })).not.toBeInTheDocument();
  });

  it('calls onNavigate when a pivot is selected', async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();

    render(
      <PivotFlyoutContent pivots={[{ pivot: pivot('root', 'Root'), dossier }]} groups={[]} onNavigate={onNavigate} />
    );

    await user.click(screen.getByRole('menuitem', { name: 'Root' }));

    expect(onNavigate).toHaveBeenCalledOnce();
  });
});
