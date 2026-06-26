/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { Hit } from 'models/entities/generated/Hit';
import { createElement, type FC, type PropsWithChildren } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { createMockEvent, createMockHit } from 'tests/utils';
import { describe, expect, it, vi } from 'vitest';
import { buildObservableEntries } from './CaseObservables';

// ---------------------------------------------------------------------------
// Pure logic tests — no React needed
// ---------------------------------------------------------------------------

describe('buildObservableEntries', () => {
  it('returns an empty array for records with no related field', () => {
    expect(buildObservableEntries([createMockHit({ howler: { id: 'h1' } })])).toEqual([]);
  });

  it('extracts a single IP from a hit', () => {
    const result = buildObservableEntries([createMockHit({ howler: { id: 'h1' }, related: { ip: ['1.2.3.4'] } })]);
    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({ type: 'ip', value: '1.2.3.4', seenIn: ['h1'] });
  });

  it('extracts multiple fields from a single record', () => {
    const result = buildObservableEntries([
      createMockHit({ howler: { id: 'h1' }, related: { ip: ['1.2.3.4'], user: ['alice'] } })
    ]);
    const types = result.map(a => a.type).sort();
    expect(types).toEqual(['ip', 'user']);
  });

  it('deduplicates the same asset value across multiple records', () => {
    const result = buildObservableEntries([
      createMockHit({ howler: { id: 'h1' }, related: { ip: ['1.2.3.4'] } }),
      createMockEvent({ howler: { id: 'obs1' }, related: { ip: ['1.2.3.4'] } })
    ]);
    expect(result).toHaveLength(1);
    expect(result[0].seenIn).toEqual(['h1', 'obs1']);
  });

  it('keeps distinct asset values as separate entries', () => {
    const result = buildObservableEntries([
      createMockHit({ howler: { id: 'h1' }, related: { ip: ['1.2.3.4'] } }),
      createMockHit({ howler: { id: 'h2' }, related: { ip: ['5.6.7.8'] } })
    ]);
    expect(result).toHaveLength(2);
  });

  it('does not duplicate seenIn ids when the same record appears twice for the same asset', () => {
    const result = buildObservableEntries([
      createMockHit({ howler: { id: 'h1' }, related: { ip: ['1.2.3.4'] } }),
      createMockHit({ howler: { id: 'h1' }, related: { ip: ['1.2.3.4'] } })
    ]);
    expect(result[0].seenIn).toEqual(['h1']);
  });

  it('skips records with no howler.id', () => {
    const noId: Partial<Hit> = { related: { ip: ['1.2.3.4'] } } as any;
    expect(buildObservableEntries([noId])).toEqual([]);
  });

  it('handles the scalar `id` field on Related', () => {
    const result = buildObservableEntries([createMockHit({ howler: { id: 'h1' }, related: { id: 'some-id' } })]);
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
    const result = buildObservableEntries([createMockHit({ howler: { id: 'h1' }, related })]);
    const types = result.map(a => a.type).sort();
    expect(types).toEqual(['hash', 'hosts', 'ids', 'signature', 'uri', 'user']);
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

vi.mock('../hooks/useCase', () => ({
  default: ({ case: c }: any) => ({ case: c, updateCase: vi.fn(), loading: false, missing: false })
}));

const mockCase = {
  case_id: 'case-001',
  items: [
    { type: 'hit', value: 'hit-1' },
    { type: 'event', value: 'obs-1' }
  ]
} as any;

const Wrapper: FC<PropsWithChildren> = ({ children }) =>
  createElement(MemoryRouter, { initialEntries: ['/cases/case-001/observables'] }, children);

// lazy import the component after mocks are set up
const CaseObservables = (await import('./CaseObservables')).default;

describe('CaseObservables component', () => {
  beforeEach(() => {
    mockDispatchApi.mockClear();
  });

  it('renders skeletons while records are loading', () => {
    mockDispatchApi.mockReturnValue(new Promise(() => {})); // never resolves

    render(<CaseObservables case={mockCase} />, { wrapper: Wrapper });

    // 6 skeleton cards
    const skeletons = document.querySelectorAll('.MuiSkeleton-root');

    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('shows "No observables found" when records have no related data', async () => {
    mockDispatchApi.mockResolvedValue({
      items: [{ howler: { id: 'hit-1' } }, { howler: { id: 'obs-1' } }]
    });

    render(<CaseObservables case={mockCase} />, { wrapper: Wrapper });

    await screen.findByText('page.cases.observables.empty');
  });

  it('renders observable cards for extracted observables', async () => {
    mockDispatchApi.mockResolvedValue({
      items: [{ howler: { id: 'hit-1' }, related: { ip: ['1.2.3.4'], user: ['alice'] } }]
    });

    render(<CaseObservables case={mockCase} />, { wrapper: Wrapper });

    await screen.findByText('1.2.3.4');

    expect(screen.getByText('alice')).toBeTruthy();
  });

  it('renders a filter chip for each observable type present', async () => {
    mockDispatchApi.mockResolvedValue({
      items: [{ howler: { id: 'hit-1' }, related: { ip: ['1.2.3.4'], user: ['alice'] } }]
    });

    render(<CaseObservables case={mockCase} />, { wrapper: Wrapper });

    await screen.findAllByText('page.cases.observables.type.ip');

    expect(screen.getAllByText('page.cases.observables.type.ip')).toHaveLength(2);
    expect(screen.getAllByText('page.cases.observables.type.user')).toHaveLength(2);
  });

  it('filters observables when a type chip is clicked', async () => {
    mockDispatchApi.mockResolvedValue({
      items: [{ howler: { id: 'hit-1' }, related: { ip: ['1.2.3.4'], user: ['alice'] } }]
    });
    render(<CaseObservables case={mockCase} />, { wrapper: Wrapper });

    // Wait for both observables to appear
    await screen.findByText('1.2.3.4');
    expect(screen.getByText('alice')).toBeTruthy();

    // Click the 'ip' filter chip
    await userEvent.click(screen.getByRole('button', { name: 'page.cases.observables.type.ip' }));

    // Alice (user) should be filtered out
    expect(screen.queryByText('alice')).toBeNull();
    expect(screen.getByText('1.2.3.4')).toBeTruthy();
  });

  it('restores all observables when an active filter chip is clicked again', async () => {
    mockDispatchApi.mockResolvedValue({
      items: [{ howler: { id: 'hit-1' }, related: { ip: ['1.2.3.4'], user: ['alice'] } }]
    });
    render(<CaseObservables case={mockCase} />, { wrapper: Wrapper });
    await screen.findByText('1.2.3.4');

    const ipChip = screen.getByRole('button', { name: 'page.cases.observables.type.ip' });
    await userEvent.click(ipChip);
    await userEvent.click(ipChip);

    expect(screen.getByText('1.2.3.4')).toBeTruthy();
    expect(screen.getByText('alice')).toBeTruthy();
  });

  it('renders nothing when the case has no hit/event items', async () => {
    const emptyCase = { case_id: 'case-002', items: [] } as any;
    render(<CaseObservables case={emptyCase} />, { wrapper: Wrapper });
    await screen.findByText('page.cases.observables.empty');
    expect(mockDispatchApi).not.toHaveBeenCalled();
  });
});
