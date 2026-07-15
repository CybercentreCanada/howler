/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import i18n from 'i18n';
import { I18nextProvider } from 'react-i18next';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import OverviewCard from './OverviewCard';

vi.mock('components/elements/display/HowlerAvatar', () => ({
  default: ({ userId }: { userId: string }) => <div id="howler-avatar">{userId}</div>
}));

vi.mock('components/elements/addons/layout/FlexOne', () => ({
  default: () => <div id="flex-one" />
}));

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <I18nextProvider i18n={i18n as any}>{children}</I18nextProvider>
);

describe('OverviewCard', () => {
  let user: UserEvent;

  beforeEach(() => {
    user = userEvent.setup();
    vi.clearAllMocks();
  });

  it('should render overview analytic and detection', () => {
    const overview = {
      overview_id: 'ov-1',
      analytic: 'Test Analytic',
      detection: 'Test Detection',
      content: 'line 1\nline 2\nline 3',
      owner: 'testuser'
    };

    render(<OverviewCard overview={overview as any} />, { wrapper: Wrapper });

    expect(screen.getByText(/Test Analytic/)).toBeInTheDocument();
    expect(screen.getByText(/Test Detection/)).toBeInTheDocument();
  });

  it('should render "All" when detection is null', () => {
    const overview = {
      overview_id: 'ov-1',
      analytic: 'Test Analytic',
      detection: null,
      content: 'line 1',
      owner: 'testuser'
    };

    render(<OverviewCard overview={overview as any} />, { wrapper: Wrapper });

    expect(screen.getByText(/All/)).toBeInTheDocument();
  });

  it('should display content preview (max 3 lines)', () => {
    const overview = {
      overview_id: 'ov-1',
      analytic: 'Test Analytic',
      detection: null,
      content: 'first line\nsecond line\nthird line\nfourth line\nfifth line',
      owner: 'testuser'
    };

    render(<OverviewCard overview={overview as any} />, { wrapper: Wrapper });

    expect(screen.getByText(/first line/)).toBeInTheDocument();
    expect(screen.getByText(/second line/)).toBeInTheDocument();
    expect(screen.getByText(/third line/)).toBeInTheDocument();
  });

  it('should render the owner avatar', () => {
    const overview = {
      overview_id: 'ov-1',
      analytic: 'Test Analytic',
      detection: null,
      content: 'content',
      owner: 'testuser'
    };

    render(<OverviewCard overview={overview as any} />, { wrapper: Wrapper });

    expect(screen.getByTestId('howler-avatar')).toBeInTheDocument();
    expect(screen.getByText('testuser')).toBeInTheDocument();
  });

  it('should not show delete button when onDelete is not provided', () => {
    const overview = {
      overview_id: 'ov-1',
      analytic: 'Test Analytic',
      detection: null,
      content: 'content',
      owner: 'testuser'
    };

    render(<OverviewCard overview={overview as any} />, { wrapper: Wrapper });

    expect(document.querySelector('[data-testid="DeleteIcon"]')).not.toBeInTheDocument();
  });

  it('should show delete button and call onDelete when clicked', async () => {
    const mockOnDelete = vi.fn();
    const overview = {
      overview_id: 'ov-1',
      analytic: 'Test Analytic',
      detection: null,
      content: 'content',
      owner: 'testuser'
    };

    render(<OverviewCard overview={overview as any} onDelete={mockOnDelete} />, { wrapper: Wrapper });

    const deleteButton = document.querySelector('[data-testid="DeleteIcon"]').closest('button');
    await user.click(deleteButton);

    expect(mockOnDelete).toHaveBeenCalledWith(expect.anything(), 'ov-1');
  });

  it('should apply custom className', () => {
    const overview = {
      overview_id: 'ov-1',
      analytic: 'Test Analytic',
      detection: null,
      content: 'content',
      owner: 'testuser'
    };

    const { container } = render(<OverviewCard overview={overview as any} className="custom-class" />, {
      wrapper: Wrapper
    });

    expect(container.querySelector('.custom-class')).toBeInTheDocument();
  });
});
