import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createElement, type FC, type PropsWithChildren } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

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

  it('renders observables in a table for extracted observables', async () => {
    mockDispatchApi.mockResolvedValue({
      items: [{ howler: { id: 'hit-1' }, related: { ip: ['1.2.3.4'], user: ['alice'] } }]
    });

    render(<CaseObservables case={mockCase} />, { wrapper: Wrapper });

    await screen.findByText('1.2.3.4');
    expect(screen.getByText('alice')).toBeTruthy();

    // Table headers should be present
    expect(screen.getByText('page.cases.observables.columns.type')).toBeTruthy();
    expect(screen.getByText('page.cases.observables.columns.value')).toBeTruthy();
  });

  it('renders a filter chip for each observable type present when popper is opened', async () => {
    mockDispatchApi.mockResolvedValue({
      items: [{ howler: { id: 'hit-1' }, related: { ip: ['1.2.3.4'], user: ['alice'] } }]
    });

    render(<CaseObservables case={mockCase} />, { wrapper: Wrapper });

    await screen.findByText('1.2.3.4');

    // Open the type filter popper
    await userEvent.click(screen.getByText('page.cases.observables.filter_by_type'));

    // Filter chips visible in popper + table = at least 2 of each type
    expect(screen.getAllByText('page.cases.observables.type.ip').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('page.cases.observables.type.user').length).toBeGreaterThanOrEqual(2);
  });

  it('filters observables when a type chip is clicked', async () => {
    mockDispatchApi.mockResolvedValue({
      items: [{ howler: { id: 'hit-1' }, related: { ip: ['1.2.3.4'], user: ['alice'] } }]
    });
    render(<CaseObservables case={mockCase} />, { wrapper: Wrapper });

    await screen.findByText('1.2.3.4');
    expect(screen.getByText('alice')).toBeTruthy();

    // Open the type filter popper and click the first 'ip' chip (in the popper)
    await userEvent.click(screen.getByText('page.cases.observables.filter_by_type'));
    await userEvent.click(screen.getAllByText('page.cases.observables.type.ip')[0]);

    expect(screen.queryByText('alice')).toBeNull();
    expect(screen.getByText('1.2.3.4')).toBeTruthy();
  });

  it('restores all observables when an active filter chip is clicked again', async () => {
    mockDispatchApi.mockResolvedValue({
      items: [{ howler: { id: 'hit-1' }, related: { ip: ['1.2.3.4'], user: ['alice'] } }]
    });
    render(<CaseObservables case={mockCase} />, { wrapper: Wrapper });
    await screen.findByText('1.2.3.4');

    // Open the type filter popper
    await userEvent.click(screen.getByText('page.cases.observables.filter_by_type'));
    const ipChip = screen.getAllByText('page.cases.observables.type.ip')[0];
    await userEvent.click(ipChip);
    await userEvent.click(ipChip);

    expect(screen.getByText('1.2.3.4')).toBeTruthy();
    expect(screen.getByText('alice')).toBeTruthy();
  });

  it('renders nothing when the case has no hit/observable items', async () => {
    const emptyCase = { case_id: 'case-002', items: [] } as any;
    render(<CaseObservables case={emptyCase} />, { wrapper: Wrapper });
    await screen.findByText('page.cases.observables.empty');
    expect(mockDispatchApi).not.toHaveBeenCalled();
  });

  it('filters observables by search query', async () => {
    mockDispatchApi.mockResolvedValue({
      items: [{ howler: { id: 'hit-1' }, related: { ip: ['1.2.3.4'], user: ['alice'] } }]
    });
    render(<CaseObservables case={mockCase} />, { wrapper: Wrapper });
    await screen.findByText('1.2.3.4');

    const searchInput = screen.getByPlaceholderText('page.cases.observables.search');
    await userEvent.type(searchInput, 'alice');

    expect(screen.queryByText('1.2.3.4')).toBeNull();
    expect(screen.getByText('alice')).toBeTruthy();
  });

  it('renders origin filter chips inside popper', async () => {
    mockDispatchApi.mockResolvedValue({
      items: [{ howler: { id: 'hit-1' }, related: { ip: ['1.2.3.4'] } }]
    });
    render(<CaseObservables case={mockCase} />, { wrapper: Wrapper });
    await screen.findByText('1.2.3.4');

    // Open the origin filter popper
    await userEvent.click(screen.getByText('page.cases.observables.filter_by_origin'));

    expect(screen.getByText('page.cases.observables.origin.hit')).toBeTruthy();
    expect(screen.getByText('page.cases.observables.origin.event')).toBeTruthy();
  });

  it('renders escalation filter chips from facet response', async () => {
    mockDispatchApi
      .mockResolvedValueOnce({
        items: [{ howler: { id: 'hit-1', escalation: 'evidence' }, related: { ip: ['1.2.3.4'] } }]
      })
      .mockResolvedValueOnce({
        'howler.escalation': { evidence: 1 }
      });

    render(<CaseObservables case={mockCase} />, { wrapper: Wrapper });
    await screen.findByText('1.2.3.4');
    await screen.findByText('page.cases.observables.filter_by_escalation');
    await userEvent.click(screen.getByText('page.cases.observables.filter_by_escalation'));

    expect(screen.getAllByText('evidence').length).toBeGreaterThanOrEqual(2);
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
    render(<CaseObservables case={mockCase} />, { wrapper: Wrapper });
    await screen.findByText('malware.exe');

    expect(screen.getByText('page.cases.observables.role.threat')).toBeTruthy();
  });
});
