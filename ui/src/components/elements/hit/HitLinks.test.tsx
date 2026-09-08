import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import PivotGroupProvider from 'components/app/providers/PivotGroupProvider';
import PivotGroupMenuItem from 'components/elements/hit/PivotGroupMenuItem';
import type { Dossier } from 'models/entities/generated/Dossier';
import { setupLocalStorageMock } from 'tests/mocks';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import HitLinks from './HitLinks';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ i18n: { language: 'en' }, t: (key: string) => key })
}));

vi.mock('components/elements/hit/related/PivotFolderMenu', () => ({
  default: ({ node }) => <span>{`group:${node.path}`}</span>
}));

const pivotLifecycle = vi.hoisted(() => ({ mounted: vi.fn(), unmounted: vi.fn() }));

vi.mock('components/elements/hit/related/PivotLink', async () => {
  const { useEffect } = await import('react');

  return {
    default: ({ pivot }) => {
      useEffect(() => {
        pivotLifecycle.mounted(pivot.value);
        return () => pivotLifecycle.unmounted(pivot.value);
      }, [pivot.value]);

      return <span>{`pivot:${pivot.value}`}</span>;
    }
  };
});

const mockLocalStorage = setupLocalStorageMock();

const dossier = {
  dossier_id: 'dossier-1',
  pivots: [
    { value: 'root', label: { en: 'Root' } },
    { value: 'example', group: 'network', label: { en: 'Example' } }
  ]
} as unknown as Dossier;

describe('HitLinks pivot grouping', () => {
  beforeEach(() => {
    mockLocalStorage.clear();
    pivotLifecycle.mounted.mockClear();
    pivotLifecycle.unmounted.mockClear();
  });

  it('replaces grouped and flat pivots without accumulating renders', async () => {
    const user = userEvent.setup();

    render(
      <PivotGroupProvider>
        <PivotGroupMenuItem />
        <HitLinks dossiers={[dossier]} />
      </PivotGroupProvider>
    );

    const toggle = screen.getByRole('switch');

    expect(screen.getAllByText('group:network')).toHaveLength(1);
    expect(screen.getAllByText('pivot:root')).toHaveLength(1);
    expect(screen.queryByText('pivot:example')).not.toBeInTheDocument();
    expect(pivotLifecycle.mounted).toHaveBeenCalledWith('root');

    await user.click(toggle);
    expect(screen.queryByText('group:network')).not.toBeInTheDocument();
    expect(screen.getAllByText('pivot:root')).toHaveLength(1);
    expect(screen.getAllByText('pivot:example')).toHaveLength(1);
    expect(pivotLifecycle.unmounted).toHaveBeenCalledWith('root');
    expect(pivotLifecycle.mounted.mock.calls.filter(([value]) => value === 'root')).toHaveLength(2);

    await user.click(toggle);
    expect(screen.getAllByText('group:network')).toHaveLength(1);
    expect(screen.getAllByText('pivot:root')).toHaveLength(1);
    expect(screen.queryByText('pivot:example')).not.toBeInTheDocument();
    expect(pivotLifecycle.unmounted.mock.calls.filter(([value]) => value === 'root')).toHaveLength(2);
    expect(pivotLifecycle.mounted.mock.calls.filter(([value]) => value === 'root')).toHaveLength(3);

    await user.click(toggle);
    expect(screen.queryByText('group:network')).not.toBeInTheDocument();
    expect(screen.getAllByText('pivot:root')).toHaveLength(1);
    expect(screen.getAllByText('pivot:example')).toHaveLength(1);
    expect(pivotLifecycle.unmounted.mock.calls.filter(([value]) => value === 'root')).toHaveLength(3);
    expect(pivotLifecycle.mounted.mock.calls.filter(([value]) => value === 'root')).toHaveLength(4);
  });

  it('does not accumulate pivots that share an action value', async () => {
    const user = userEvent.setup();
    const repeatedValueDossier = {
      dossier_id: 'dossier-1',
      pivots: [
        { value: 'example', group: 'network', label: { en: 'Network Example' } },
        { value: 'example', group: 'host', label: { en: 'Host Example' } }
      ]
    } as unknown as Dossier;

    render(
      <PivotGroupProvider>
        <PivotGroupMenuItem />
        <HitLinks dossiers={[repeatedValueDossier]} />
      </PivotGroupProvider>
    );

    const toggle = screen.getByRole('switch');

    await user.click(toggle);
    expect(screen.getAllByText('pivot:example')).toHaveLength(2);

    await user.click(toggle);
    await user.click(toggle);
    expect(screen.getAllByText('pivot:example')).toHaveLength(2);

    await user.click(toggle);
    await user.click(toggle);
    expect(screen.getAllByText('pivot:example')).toHaveLength(2);
  });
});
