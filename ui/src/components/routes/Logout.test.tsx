import { render, screen } from '@testing-library/react';
import i18n from 'i18n';
import { I18nextProvider } from 'react-i18next';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Logout from './Logout';

const mockHideMenus = vi.fn();
const mockClear = vi.fn();

vi.mock('commons/components/app/hooks', () => ({
  useAppBanner: () => <div data-testid="app-banner">Banner</div>,
  useAppLayout: () => ({
    hideMenus: mockHideMenus
  })
}));

vi.mock('components/hooks/useMyLocalStorage', () => ({
  default: () => ({
    clear: mockClear
  })
}));

vi.mock('commons/components/pages/PageCardCentered', () => ({
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>
}));

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <I18nextProvider i18n={i18n as any}>{children}</I18nextProvider>
);

describe('Logout', () => {
  const originalLocation = window.location;

  beforeEach(() => {
    vi.useFakeTimers();
    // Mock window.location.replace
    Object.defineProperty(window, 'location', {
      value: { ...originalLocation, replace: vi.fn() },
      writable: true
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    Object.defineProperty(window, 'location', { value: originalLocation, writable: true });
    vi.clearAllMocks();
  });

  it('should render the logout message', () => {
    render(<Logout />, { wrapper: Wrapper });

    expect(screen.getByText(/Logging out current user/)).toBeInTheDocument();
  });

  it('should render the app banner', () => {
    render(<Logout />, { wrapper: Wrapper });

    expect(screen.getByText('Banner')).toBeInTheDocument();
  });

  it('should hide menus on mount', () => {
    render(<Logout />, { wrapper: Wrapper });

    expect(mockHideMenus).toHaveBeenCalled();
  });

  it('should clear localStorage and redirect after 2 seconds', () => {
    render(<Logout />, { wrapper: Wrapper });

    expect(mockClear).not.toHaveBeenCalled();

    vi.advanceTimersByTime(2000);

    expect(mockClear).toHaveBeenCalled();
    expect(window.location.replace).toHaveBeenCalledWith('/');
  });
});
