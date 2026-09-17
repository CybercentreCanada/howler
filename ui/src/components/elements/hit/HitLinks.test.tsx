import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { Dossier } from 'models/entities/generated/Dossier';
import { setupLocalStorageMock } from 'tests/mocks';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import HitLinks from './HitLinks';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ i18n: { language: 'en' }, t: (key: string) => key })
}));

vi.mock('components/elements/hit/related/pivots/PivotFolderMenu', () => ({
  default: ({ node }: any) => <span>{`group:${node.path}`}</span>
}));

const pivotLifecycle = vi.hoisted(() => ({ mounted: vi.fn(), unmounted: vi.fn() }));

vi.mock('components/elements/hit/related/pivots/PivotLink', async () => {
  const { useEffect } = await import('react');

  return {
    default: ({ pivot }: any) => {
      useEffect(() => {
        pivotLifecycle.mounted(pivot.value);
        return () => pivotLifecycle.unmounted(pivot.value);
      }, [pivot.value]);

      return <span>{`pivot:${pivot.value}`}</span>;
    }
  };
});

vi.mock('components/elements/hit/related/RelatedLink', () => ({
  default: ({ title, href }: { title?: string; href?: string }) => <a href={href}>{title}</a>
}));

const mockLocalStorage = setupLocalStorageMock();

const dossier = {
  dossier_id: 'dossier-1',
  pivots: [
    { value: 'root', label: { en: 'Root' } },
    { value: 'example', group: 'network', label: { en: 'Example' } },
    { value: 'example-two', group: 'network', label: { en: 'Example Two' } }
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
      <>
        <HitLinks dossiers={[dossier]} />
      </>
    );

    const toggle = screen.getByRole('switch');

    expect(screen.getByText('group:network')).toBeInTheDocument();
    expect(screen.getAllByText('pivot:root')).toHaveLength(1);
    expect(screen.queryByText('pivot:example')).not.toBeInTheDocument();
    expect(pivotLifecycle.mounted).toHaveBeenCalledWith('root');

    await user.click(toggle);
    expect(screen.queryByText('group:network')).not.toBeInTheDocument();
    expect(screen.getAllByText('pivot:root')).toHaveLength(1);
    expect(screen.getAllByText('pivot:example')).toHaveLength(1);
    expect(screen.getAllByText('pivot:example-two')).toHaveLength(1);
    expect(pivotLifecycle.unmounted).toHaveBeenCalledWith('root');
    expect(pivotLifecycle.mounted.mock.calls.filter(([value]) => value === 'root')).toHaveLength(2);

    await user.click(toggle);
    expect(screen.getByText('group:network')).toBeInTheDocument();
    expect(screen.getAllByText('pivot:root')).toHaveLength(1);
    expect(screen.queryByText('pivot:example')).not.toBeInTheDocument();
    expect(screen.queryByText('pivot:example-two')).not.toBeInTheDocument();

    await user.click(toggle);
    expect(screen.queryByText('group:network')).not.toBeInTheDocument();
    expect(screen.getAllByText('pivot:root')).toHaveLength(1);
    expect(screen.getAllByText('pivot:example')).toHaveLength(1);
    expect(screen.getAllByText('pivot:example-two')).toHaveLength(1);
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

    render(<HitLinks dossiers={[repeatedValueDossier]} />);

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

  it('renders at most three unique external links and omits empty hrefs', () => {
    render(
      <HitLinks
        hit={
          {
            howler: {
              links: [
                { href: 'https://one.example', title: 'One' },
                { href: 'https://two.example', title: 'Two' },
                { href: 'https://three.example', title: 'Three' },
                { href: '', title: 'Empty' },
                { href: 'https://four.example', title: 'Four' }
              ]
            }
          } as any
        }
      />
    );

    expect(screen.getByRole('link', { name: 'One' })).toBeInTheDocument();
    expect(screen.queryByText('Empty')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Two' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Three' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Four' })).not.toBeInTheDocument();
  });

  it('renders nothing when there are no links, pivots, or notebooks', () => {
    const { container } = render(<HitLinks />);

    expect(container).toBeEmptyDOMElement();
  });
});
