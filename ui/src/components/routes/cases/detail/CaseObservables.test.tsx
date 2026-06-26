/// <reference types="vitest" />
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
