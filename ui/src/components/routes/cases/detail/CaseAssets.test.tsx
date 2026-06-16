/// <reference types="vitest" />
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { Hit } from 'models/entities/generated/Hit';
import { createElement, type FC, type PropsWithChildren } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { createMockCase, createMockHit, createMockObservable } from 'tests/utils';
import { describe, expect, it, vi } from 'vitest';
import { buildAssetEntries, classifyRole } from './CaseAssets';

// ---------------------------------------------------------------------------
// Pure logic tests — no React needed
// ---------------------------------------------------------------------------

describe('buildAssetEntries', () => {
  it('returns an empty array for records with no related field', () => {
    expect(buildAssetEntries([createMockHit({ howler: { id: 'h1' } })])).toEqual([]);
  });

  it('extracts a single IP from a hit', () => {
    const result = buildAssetEntries([createMockHit({ howler: { id: 'h1' }, related: { ip: ['1.2.3.4'] } })]);
    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({ type: 'ip', value: '1.2.3.4', seenIn: ['h1'] });
  });

  it('extracts multiple fields from a single record', () => {
    const result = buildAssetEntries([
      createMockHit({ howler: { id: 'h1' }, related: { ip: ['1.2.3.4'], user: ['alice'] } })
    ]);
    const types = result.map(a => a.type).sort();
    expect(types).toEqual(['ip', 'user']);
  });

  it('deduplicates the same asset value across multiple records', () => {
    const result = buildAssetEntries([
      createMockHit({ howler: { id: 'h1' }, related: { ip: ['1.2.3.4'] } }),
      createMockObservable({ howler: { id: 'obs1' }, related: { ip: ['1.2.3.4'] } })
    ]);
    expect(result).toHaveLength(1);
    expect(result[0].seenIn).toEqual(['h1', 'obs1']);
  });

  it('keeps distinct asset values as separate entries', () => {
    const result = buildAssetEntries([
      createMockHit({ howler: { id: 'h1' }, related: { ip: ['1.2.3.4'] } }),
      createMockHit({ howler: { id: 'h2' }, related: { ip: ['5.6.7.8'] } })
    ]);
    expect(result).toHaveLength(2);
  });

  it('does not duplicate seenIn ids when the same record appears twice for the same asset', () => {
    const result = buildAssetEntries([
      createMockHit({ howler: { id: 'h1' }, related: { ip: ['1.2.3.4'] } }),
      createMockHit({ howler: { id: 'h1' }, related: { ip: ['1.2.3.4'] } })
    ]);
    expect(result[0].seenIn).toEqual(['h1']);
  });

  it('skips records with no howler.id', () => {
    const noId: Partial<Hit> = { related: { ip: ['1.2.3.4'] } } as any;
    expect(buildAssetEntries([noId])).toEqual([]);
  });

  it('handles the scalar `id` field on Related', () => {
    const result = buildAssetEntries([createMockHit({ howler: { id: 'h1' }, related: { id: 'some-id' } })]);
    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({ type: 'id', value: 'some-id', seenIn: ['h1'] });
  });

  it('handles array fields like hash, hosts, user, ids, uri, signature', () => {
    const related = {
      hash: ['abc123'],
      hosts: ['host.example.com'],
      user: ['bob'],
      ids: ['guid-1'],
      uri: ['https://example.com'],
      signature: ['rule-X']
    };
    const result = buildAssetEntries([createMockHit({ howler: { id: 'h1' }, related })]);
    const types = result.map(a => a.type).sort();
    expect(types).toEqual(['hash', 'hosts', 'ids', 'signature', 'uri', 'user']);
  });
});

// ---------------------------------------------------------------------------
// classifyRole tests
// ---------------------------------------------------------------------------

describe('classifyRole', () => {
  const emptyCase = createMockCase();

  it('returns "threat" when value is in case.threats', () => {
    const _case = createMockCase({ threats: ['malicious.exe'] });
    const records = [createMockHit({ howler: { id: 'h1' } })];
    expect(classifyRole('malicious.exe', _case, records)).toBe('threat');
  });

  it('returns "target" when value is in case.targets', () => {
    const _case = createMockCase({ targets: ['server-01'] });
    const records = [createMockHit({ howler: { id: 'h1' } })];
    expect(classifyRole('server-01', _case, records)).toBe('target');
  });

  it('returns "indicator" when value is in case.indicators', () => {
    const _case = createMockCase({ indicators: ['1.2.3.4'] });
    const records = [createMockHit({ howler: { id: 'h1' } })];
    expect(classifyRole('1.2.3.4', _case, records)).toBe('indicator');
  });

  it('returns "threat" when value matches howler.outline.threat', () => {
    const records = [createMockHit({ howler: { id: 'h1', outline: { threat: 'malicious.exe' } } })];
    expect(classifyRole('malicious.exe', emptyCase, records)).toBe('threat');
  });

  it('returns "threat" with case-insensitive matching', () => {
    const records = [createMockHit({ howler: { id: 'h1', outline: { threat: 'Malicious.EXE' } } })];
    expect(classifyRole('malicious.exe', emptyCase, records)).toBe('threat');
  });

  it('does not match threat by substring — only exact match', () => {
    const records = [createMockHit({ howler: { id: 'h1', outline: { threat: 'evil.com dropped payload' } } })];
    // No substring match, defaults to indicator
    expect(classifyRole('evil.com', emptyCase, records)).toBe('indicator');
  });

  it('classifies as indicator when value is in outline.indicators but not in threat/target', () => {
    const records = [
      createMockHit({
        howler: { id: 'h1', outline: { threat: 'actor-x', target: 'server-01', indicators: ['1.2.3.4'] } }
      })
    ];
    expect(classifyRole('1.2.3.4', emptyCase, records)).toBe('indicator');
  });

  it('returns "target" when value matches howler.outline.target', () => {
    const records = [createMockHit({ howler: { id: 'h1', outline: { target: 'server-01' } } })];
    expect(classifyRole('server-01', emptyCase, records)).toBe('target');
  });

  it('returns "indicator" when value matches threat.indicator.ip', () => {
    const records = [
      createMockHit({
        howler: { id: 'h1' },
        threat: { indicator: { ip: '10.0.0.1' } }
      })
    ];
    expect(classifyRole('10.0.0.1', emptyCase, records)).toBe('indicator');
  });

  it('returns "indicator" when value matches threat.indicator.description', () => {
    const records = [
      createMockHit({
        howler: { id: 'h1' },
        threat: { indicator: { description: 'suspicious-hash-abc123' } }
      })
    ];
    expect(classifyRole('suspicious-hash-abc123', emptyCase, records)).toBe('indicator');
  });

  it('defaults to "indicator" when value has no specific classification', () => {
    const records = [createMockHit({ howler: { id: 'h1' }, related: { ip: ['5.6.7.8'] } })];
    expect(classifyRole('5.6.7.8', emptyCase, records)).toBe('indicator');
  });

  it('case-level threats take priority over per-record outline.target', () => {
    const _case = createMockCase({ threats: ['dual-use.exe'] });
    const records = [createMockHit({ howler: { id: 'h1', outline: { target: 'dual-use.exe' } } })];
    expect(classifyRole('dual-use.exe', _case, records)).toBe('threat');
  });

  it('trims whitespace before comparing', () => {
    const records = [createMockHit({ howler: { id: 'h1', outline: { threat: '  evil.com  ' } } })];
    expect(classifyRole('evil.com', emptyCase, records)).toBe('threat');
  });
});

// ---------------------------------------------------------------------------
// Component rendering tests
// ---------------------------------------------------------------------------

const mockDispatchApi = vi.fn();

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key, i18n: { language: 'en' } })
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('api', () => ({
  default: {
    v2: {
      search: {
        post: vi.fn(() => Promise.resolve({ items: [] })),
        facet: {
          post: vi.fn(() => Promise.resolve({}))
        }
      }
    }
  }
}));

vi.mock('../hooks/useCase', () => ({
  default: ({ case: c }: any) => ({ case: c, updateCase: vi.fn(), loading: false, missing: false })
}));

vi.mock('components/elements/PluginTypography', () => ({
  default: ({ value }: any) => createElement('span', null, value)
}));

const mockCase = {
  case_id: 'case-001',
  items: [
    { type: 'hit', value: 'hit-1', path: 'alerts/analytic-1 (hit-1)' },
    { type: 'observable', value: 'obs-1', path: 'observables/obs-1' }
  ]
} as any;

const Wrapper: FC<PropsWithChildren> = ({ children }) =>
  createElement(MemoryRouter, { initialEntries: ['/cases/case-001/assets'] }, children);

// lazy import the component after mocks are set up
const CaseAssets = (await import('./CaseAssets')).default;

describe('CaseAssets component', () => {
  beforeEach(() => {
    mockDispatchApi.mockClear();
  });

  it('renders skeletons while records are loading', () => {
    mockDispatchApi.mockReturnValue(new Promise(() => {})); // never resolves

    render(<CaseAssets case={mockCase} />, { wrapper: Wrapper });

    const skeletons = document.querySelectorAll('.MuiSkeleton-root');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('shows "No assets found" when records have no related data', async () => {
    mockDispatchApi.mockResolvedValue({
      items: [{ howler: { id: 'hit-1' } }, { howler: { id: 'obs-1' } }]
    });

    render(<CaseAssets case={mockCase} />, { wrapper: Wrapper });

    await screen.findByText('page.cases.assets.empty');
  });

  it('renders assets in a table for extracted assets', async () => {
    mockDispatchApi.mockResolvedValue({
      items: [{ howler: { id: 'hit-1' }, related: { ip: ['1.2.3.4'], user: ['alice'] } }]
    });

    render(<CaseAssets case={mockCase} />, { wrapper: Wrapper });

    await screen.findByText('1.2.3.4');
    expect(screen.getByText('alice')).toBeTruthy();

    // Table headers should be present
    expect(screen.getByText('page.cases.assets.columns.type')).toBeTruthy();
    expect(screen.getByText('page.cases.assets.columns.value')).toBeTruthy();
  });

  it('renders a filter chip for each asset type present when popper is opened', async () => {
    mockDispatchApi.mockResolvedValue({
      items: [{ howler: { id: 'hit-1' }, related: { ip: ['1.2.3.4'], user: ['alice'] } }]
    });

    render(<CaseAssets case={mockCase} />, { wrapper: Wrapper });

    await screen.findByText('1.2.3.4');

    // Open the type filter popper
    await userEvent.click(screen.getByText('page.cases.assets.filter_by_type'));

    // Filter chips visible in popper + table = at least 2 of each type
    expect(screen.getAllByText('page.cases.assets.type.ip').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('page.cases.assets.type.user').length).toBeGreaterThanOrEqual(2);
  });

  it('filters assets when a type chip is clicked', async () => {
    mockDispatchApi.mockResolvedValue({
      items: [{ howler: { id: 'hit-1' }, related: { ip: ['1.2.3.4'], user: ['alice'] } }]
    });
    render(<CaseAssets case={mockCase} />, { wrapper: Wrapper });

    await screen.findByText('1.2.3.4');
    expect(screen.getByText('alice')).toBeTruthy();

    // Open the type filter popper and click the first 'ip' chip (in the popper)
    await userEvent.click(screen.getByText('page.cases.assets.filter_by_type'));
    await userEvent.click(screen.getAllByText('page.cases.assets.type.ip')[0]);

    expect(screen.queryByText('alice')).toBeNull();
    expect(screen.getByText('1.2.3.4')).toBeTruthy();
  });

  it('restores all assets when an active filter chip is clicked again', async () => {
    mockDispatchApi.mockResolvedValue({
      items: [{ howler: { id: 'hit-1' }, related: { ip: ['1.2.3.4'], user: ['alice'] } }]
    });
    render(<CaseAssets case={mockCase} />, { wrapper: Wrapper });
    await screen.findByText('1.2.3.4');

    // Open the type filter popper
    await userEvent.click(screen.getByText('page.cases.assets.filter_by_type'));
    const ipChip = screen.getAllByText('page.cases.assets.type.ip')[0];
    await userEvent.click(ipChip);
    await userEvent.click(ipChip);

    expect(screen.getByText('1.2.3.4')).toBeTruthy();
    expect(screen.getByText('alice')).toBeTruthy();
  });

  it('renders nothing when the case has no hit/observable items', async () => {
    const emptyCase = { case_id: 'case-002', items: [] } as any;
    render(<CaseAssets case={emptyCase} />, { wrapper: Wrapper });
    await screen.findByText('page.cases.assets.empty');
    expect(mockDispatchApi).not.toHaveBeenCalled();
  });

  it('filters assets by search query', async () => {
    mockDispatchApi.mockResolvedValue({
      items: [{ howler: { id: 'hit-1' }, related: { ip: ['1.2.3.4'], user: ['alice'] } }]
    });
    render(<CaseAssets case={mockCase} />, { wrapper: Wrapper });
    await screen.findByText('1.2.3.4');

    const searchInput = screen.getByPlaceholderText('page.cases.assets.search');
    await userEvent.type(searchInput, 'alice');

    expect(screen.queryByText('1.2.3.4')).toBeNull();
    expect(screen.getByText('alice')).toBeTruthy();
  });

  it('renders origin filter chips inside popper', async () => {
    mockDispatchApi.mockResolvedValue({
      items: [{ howler: { id: 'hit-1' }, related: { ip: ['1.2.3.4'] } }]
    });
    render(<CaseAssets case={mockCase} />, { wrapper: Wrapper });
    await screen.findByText('1.2.3.4');

    // Open the origin filter popper
    await userEvent.click(screen.getByText('page.cases.assets.filter_by_origin'));

    expect(screen.getByText('page.cases.assets.origin.hit')).toBeTruthy();
    expect(screen.getByText('page.cases.assets.origin.observable')).toBeTruthy();
  });

  it('renders escalation filter chips from facet response', async () => {
    mockDispatchApi
      .mockResolvedValueOnce({
        items: [{ howler: { id: 'hit-1', escalation: 'evidence' }, related: { ip: ['1.2.3.4'] } }]
      })
      .mockResolvedValueOnce({
        'howler.escalation': { evidence: 1 }
      });

    render(<CaseAssets case={mockCase} />, { wrapper: Wrapper });
    await screen.findByText('1.2.3.4');
    await waitFor(() => {
      // 'evidence' appears in the table escalation column
      expect(screen.getByText('evidence')).toBeTruthy();
    });
  });

  it('classifies roles and renders role chips in the table', async () => {
    mockDispatchApi.mockResolvedValue({
      items: [
        {
          howler: { id: 'hit-1', outline: { threat: 'malware.exe' } },
          related: { hosts: ['malware.exe'] }
        }
      ]
    });
    render(<CaseAssets case={mockCase} />, { wrapper: Wrapper });
    await screen.findByText('malware.exe');

    expect(screen.getByText('page.cases.assets.role.threat')).toBeTruthy();
  });
});
