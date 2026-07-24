// @ts-nocheck
import { createEvent, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { SocketContext } from 'components/app/providers/SocketProvider';
import type { Hit } from 'models/entities/generated/Hit';
import howlerPluginStore from 'plugins/store';
import type { FC, PropsWithChildren, ReactNode } from 'react';
import { createMockHit } from 'tests/utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import HitBanner from './HitBanner';
import { HitLayout } from './HitLayout';

const executeFunctionMock = vi.hoisted(() => vi.fn());
const stringToColorMock = vi.hoisted(() => vi.fn(() => '#123456'));

vi.mock('react-pluggable', async () => {
  const actual = await vi.importActual('react-pluggable');

  return {
    ...actual,
    usePluginStore: () => ({ executeFunction: executeFunctionMock })
  };
});

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: { count?: number; duration?: string }) => {
      if (options?.count !== undefined) {
        return `${key}:${options.count}`;
      }

      if (options?.duration) {
        return `${key}:${options.duration}`;
      }

      return key;
    }
  }),
  Trans: ({ i18nKey }: { i18nKey: string }) => <span>{i18nKey}</span>
}));

vi.mock('commons/components/app/hooks', () => ({
  useAppUser: () => ({ user: { username: 'current-user' } })
}));

vi.mock('components/elements/display/HowlerAvatar', () => ({
  default: ({ userId }: { userId: string }) => <div id={`avatar-${userId}`}>{userId}</div>
}));

vi.mock('utils/utils', async () => {
  const actual = await vi.importActual('utils/utils');

  return {
    ...actual,
    stringToColor: stringToColorMock
  };
});

vi.mock('./elements/AnalyticLink', () => ({
  default: () => <div id="analytic-link">analytic-link</div>
}));

vi.mock('./related/RelatedRecords', () => ({
  default: () => <div id="related-records">related-records</div>
}));

const mockConfig = {
  indexes: {},
  lookups: {},
  configuration: {
    system: {
      retention: {
        limit_amount: 350,
        limit_unit: 'days'
      }
    }
  },
  c12nDef: {},
  mapping: {}
};

const createWrapper = (viewers: Record<string, string[]> = {}): FC<PropsWithChildren> => {
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <ApiConfigContext.Provider value={{ config: mockConfig, setConfig: vi.fn() } as any}>
      <SocketContext.Provider
        value={
          {
            viewers,
            addListener: vi.fn(),
            removeListener: vi.fn(),
            emit: vi.fn(),
            status: 1,
            reconnect: vi.fn(),
            open: true,
            fetchViewers: vi.fn()
          } as any
        }
      >
        {children}
      </SocketContext.Provider>
    </ApiConfigContext.Provider>
  );

  return Wrapper;
};

const createBannerHit = (overrides?: Partial<Hit>): Hit =>
  createMockHit({
    organization: { id: 'org-1', name: 'Test Org' } as any,
    event: { provider: 'howler', created: '2024-01-01T00:00:00Z' } as any,
    howler: {
      id: 'hit-123',
      analytic: 'Analytic Name',
      detection: 'Detection Name',
      status: 'open',
      assignment: 'analyst-1',
      escalation: 'hit',
      rationale: 'Escalation rationale',
      related: [],
      outline: {
        threat: 'Threat value',
        target: 'Target value',
        indicators: ['ioc-a', 'ioc-b'],
        summary: 'Summary value'
      },
      links: [{ href: 'https://example.com', title: 'Open source link' }]
    } as any,
    ...overrides
  } as any);

const renderHitBanner = ({
  hit = createBannerHit(),
  layout = HitLayout.NORMAL,
  showAssigned = true,
  viewers = {}
}: {
  hit?: Hit;
  layout?: HitLayout;
  showAssigned?: boolean;
  viewers?: Record<string, string[]>;
} = {}) =>
  render(<HitBanner hit={hit} layout={layout} showAssigned={showAssigned} />, {
    wrapper: createWrapper(viewers)
  });

describe('HitBanner', () => {
  beforeEach(() => {
    howlerPluginStore.plugins.splice(0, howlerPluginStore.plugins.length);
    executeFunctionMock.mockReset();
    stringToColorMock.mockClear();
  });

  afterEach(() => {
    howlerPluginStore.plugins.splice(0, howlerPluginStore.plugins.length);
  });

  it('renders the main banner sections for a fully populated hit', () => {
    renderHitBanner();

    expect(screen.getByText('Test Org')).toBeInTheDocument();
    expect(screen.getByTestId('analytic-link')).toBeInTheDocument();
    expect(screen.getByText('hit.header.rationale: Escalation rationale')).toBeInTheDocument();
    expect(screen.getByText('hit.header.threat:')).toBeInTheDocument();
    expect(screen.getByText('Threat value')).toBeInTheDocument();
    expect(screen.getByText('hit.header.target:')).toBeInTheDocument();
    expect(screen.getByText('Target value')).toBeInTheDocument();
    expect(screen.getByText('hit.header.indicators:')).toBeInTheDocument();
    expect(screen.getByText('ioc-a')).toBeInTheDocument();
    expect(screen.getByText('ioc-b')).toBeInTheDocument();
    expect(screen.getByText('hit.header.summary:')).toBeInTheDocument();
    expect(screen.getByText('Summary value')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open source link' })).toHaveAttribute('href', 'https://example.com');
  });

  it.each(['in-progress', 'on-hold'])('renders the status chip for %s', status => {
    const hit = createBannerHit({ howler: { ...createBannerHit().howler, status } as any } as any);

    renderHitBanner({ hit });

    expect(screen.getByText(status)).toBeInTheDocument();
  });

  it('hides and shows the unassigned chip based on showAssigned', () => {
    const hit = createBannerHit({ howler: { ...createBannerHit().howler, assignment: 'unassigned' } as any } as any);

    renderHitBanner({ hit, showAssigned: false });

    expect(screen.queryByText('app.drawer.hit.assignment.unassigned.name')).not.toBeInTheDocument();

    renderHitBanner({ hit, showAssigned: true });

    expect(screen.getByText('app.drawer.hit.assignment.unassigned.name')).toBeInTheDocument();
  });

  it('renders related records only when related hits are present', () => {
    const withRelated = createBannerHit({ howler: { ...createBannerHit().howler, related: ['hit-2'] } as any } as any);

    renderHitBanner({ hit: withRelated });

    expect(screen.getByTestId('related-records')).toBeInTheDocument();
  });

  it('uses stringToColor for unknown providers and skips it for known providers', () => {
    const unknownProviderHit = createBannerHit({
      event: { provider: 'custom-provider', created: '2024-01-01T00:00:00Z' } as any
    });

    renderHitBanner({ hit: unknownProviderHit });

    expect(stringToColorMock).toHaveBeenCalledWith('custom-provider');

    stringToColorMock.mockClear();

    const knownProviderHit = createBannerHit({ event: { provider: 'howler', created: '2024-01-01T00:00:00Z' } as any });

    renderHitBanner({ hit: knownProviderHit });

    expect(stringToColorMock).not.toHaveBeenCalled();
  });

  it('renders plugin status sections from plugin hooks', () => {
    howlerPluginStore.plugins.push('demo-plugin');
    executeFunctionMock.mockImplementation((name: string) => {
      if (name === 'demo-plugin.status') {
        return <span id="plugin-status">plugin-status</span>;
      }

      return null;
    });

    const hit = createBannerHit();

    renderHitBanner({ hit, layout: HitLayout.COMFY });

    expect(screen.getByTestId('plugin-status')).toBeInTheDocument();
    expect(executeFunctionMock).toHaveBeenCalledWith('demo-plugin.status', { hit, layout: HitLayout.COMFY });
  });

  it('prevents default navigation when the banner root link is clicked', () => {
    const { container } = renderHitBanner();
    const rootLink = container.querySelector('a[href="/hits/hit-123"]');

    expect(rootLink).toBeTruthy();

    const clickEvent = createEvent.click(rootLink!, {
      bubbles: true,
      cancelable: true
    });

    fireEvent(rootLink!, clickEvent);

    expect(clickEvent.defaultPrevented).toBe(true);
  });

  it('stops propagation when the external link chip is clicked', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();

    render(
      <div onClick={onClick}>
        <HitBanner hit={createBannerHit()} layout={HitLayout.NORMAL} />
      </div>,
      { wrapper: createWrapper() }
    );

    await user.click(screen.getByRole('link', { name: 'Open source link' }));

    expect(onClick).not.toHaveBeenCalled();
  });

  it('renders fallback link label and omits optional outline/rationale sections when missing', () => {
    const hit = createBannerHit({
      organization: { id: null, name: null } as any,
      event: { provider: null, created: '2024-01-01T00:00:00Z' } as any,
      howler: {
        ...createBannerHit().howler,
        rationale: null,
        outline: {} as any,
        links: [{ href: 'https://example.com' }],
        status: 'open'
      } as any
    } as any);

    renderHitBanner({ hit, layout: HitLayout.DENSE });

    expect(screen.getByText('unknown')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'hit.header.link' })).toHaveAttribute('href', 'https://example.com');
    expect(screen.queryByText('hit.header.rationale:')).not.toBeInTheDocument();
    expect(screen.queryByText('hit.header.threat:')).not.toBeInTheDocument();
    expect(screen.queryByText('hit.header.target:')).not.toBeInTheDocument();
    expect(screen.queryByText('hit.header.summary:')).not.toBeInTheDocument();
  });
});
