import { render, screen, waitFor } from '@testing-library/react';
import i18n from 'i18n';
import React from 'react';
import { I18nextProvider } from 'react-i18next';
import { setupContextSelectorMock } from 'tests/mocks';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AddNewCard from './AddNewCard';

setupContextSelectorMock();

const mockApiSearchAnalyticPost = vi.fn();
vi.mock('api', () => ({
  default: {
    search: {
      analytic: {
        post: (...args: any[]) => mockApiSearchAnalyticPost(...args)
      }
    }
  }
}));

vi.mock('components/elements/addons/buttons/CustomButton', () => ({
  default: ({ children, disabled, onClick, ...props }: any) => (
    <button disabled={disabled} onClick={onClick} {...props}>
      {children}
    </button>
  )
}));

const mockFetchViews = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));

vi.mock('components/app/providers/ViewProvider', () => ({
  ViewContext: React.createContext({
    views: {
      'view-1': {
        view_id: 'view-1',
        title: 'My View',
        query: 'howler.status:open',
        sort: 'event.created desc',
        span: 'date.range.1.month',
        type: 'personal',
        owner: 'testuser',
        settings: { advance_on_triage: false }
      },
      'view-2': {
        view_id: 'view-2',
        title: 'Second View',
        query: 'howler.status:open',
        sort: 'event.created desc',
        span: 'date.range.1.month',
        type: 'personal',
        owner: 'testuser',
        settings: { advance_on_triage: false }
      }
    },
    fetchViews: mockFetchViews
  })
}));

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <I18nextProvider i18n={i18n as any}>{children}</I18nextProvider>
);

describe('AddNewCard', () => {
  const mockAddCard = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockApiSearchAnalyticPost.mockResolvedValue({
      items: [{ analytic_id: 'analytic-1', name: 'Test Analytic', description: 'Test description' }],
      total: 1
    });
  });

  it('should render the add card title', async () => {
    render(<AddNewCard dashboard={[]} addCard={mockAddCard} />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText('Add New Panel')).toBeInTheDocument();
    });
  });

  it('should render the description', async () => {
    render(<AddNewCard dashboard={[]} addCard={mockAddCard} />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText(/Add an additional panel/)).toBeInTheDocument();
    });
  });

  it('should have the create button disabled initially', async () => {
    render(<AddNewCard dashboard={[]} addCard={mockAddCard} />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Create/i })).toBeDisabled();
    });
  });

  it('should fetch analytics on mount', async () => {
    render(<AddNewCard dashboard={[]} addCard={mockAddCard} />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(mockApiSearchAnalyticPost).toHaveBeenCalledWith(expect.objectContaining({ query: '*:*' }));
    });
  });
});
