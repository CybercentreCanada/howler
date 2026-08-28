/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import i18n from 'i18n';
import { I18nextProvider } from 'react-i18next';
import { MemoryRouter, useLocation, useNavigate } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import ErrorBoundary from './ErrorBoundary';

vi.mock('react-pluggable', () => ({
  usePluginStore: () => ({
    executeFunction: vi.fn(() => null)
  })
}));

vi.mock('plugins/store', () => ({
  default: { plugins: [] }
}));

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <I18nextProvider i18n={i18n as any}>{children}</I18nextProvider>
);

const ThrowingComponent = ({ error }: { error: Error }) => {
  throw error;
};

const RouteContent = () => {
  const location = useLocation();

  if (location.pathname === '/broken') {
    return <ThrowingComponent error={new Error('Broken route')} />;
  }

  return <div>Recovered route</div>;
};

const NavigationButton = () => {
  const navigate = useNavigate();

  return <button onClick={() => navigate('/recovered')}>Navigate away</button>;
};

describe('ErrorBoundary', () => {
  it('should render children when no error occurs', () => {
    render(
      <MemoryRouter>
        <ErrorBoundary>
          <div>Child content</div>
        </ErrorBoundary>
      </MemoryRouter>,
      { wrapper: Wrapper }
    );

    expect(screen.getByText('Child content')).toBeInTheDocument();
  });

  it('should render error UI when a child throws', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const testError = new Error('Test error message');
    testError.stack = 'Error: Test error message\n    at TestComponent';

    render(
      <MemoryRouter>
        <ErrorBoundary>
          <ThrowingComponent error={testError} />
        </ErrorBoundary>
      </MemoryRouter>,
      { wrapper: Wrapper }
    );

    expect(screen.getByText('Test error message')).toBeInTheDocument();

    consoleSpy.mockRestore();
  });

  it('should display the error page title when an error occurs', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const testError = new Error('Something went wrong');

    render(
      <MemoryRouter>
        <ErrorBoundary>
          <ThrowingComponent error={testError} />
        </ErrorBoundary>
      </MemoryRouter>,
      { wrapper: Wrapper }
    );

    expect(screen.getByText('Application Stopped Working')).toBeInTheDocument();

    consoleSpy.mockRestore();
  });

  it('should reset after navigating away from an error', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={['/broken']}>
        <NavigationButton />
        <ErrorBoundary>
          <RouteContent />
        </ErrorBoundary>
      </MemoryRouter>,
      { wrapper: Wrapper }
    );

    expect(screen.getByText('Broken route')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Navigate away' }));

    expect(screen.queryByText('Broken route')).not.toBeInTheDocument();
    expect(screen.getByText('Recovered route')).toBeInTheDocument();

    consoleSpy.mockRestore();
  });
});
