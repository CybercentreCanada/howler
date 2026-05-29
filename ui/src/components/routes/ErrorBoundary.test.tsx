/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import i18n from 'i18n';
import { I18nextProvider } from 'react-i18next';
import { describe, expect, it, vi } from 'vitest';
import ErrorBoundary from './ErrorBoundary';

vi.mock('commons/components/pages/PageCenter', () => ({
  default: ({ children }: { children: React.ReactNode }) => <div id="page-center">{children}</div>
}));

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

describe('ErrorBoundary', () => {
  it('should render children when no error occurs', () => {
    render(
      <ErrorBoundary>
        <div>Child content</div>
      </ErrorBoundary>,
      { wrapper: Wrapper }
    );

    expect(screen.getByText('Child content')).toBeInTheDocument();
  });

  it('should render error UI when a child throws', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const testError = new Error('Test error message');
    testError.stack = 'Error: Test error message\n    at TestComponent';

    render(
      <ErrorBoundary>
        <ThrowingComponent error={testError} />
      </ErrorBoundary>,
      { wrapper: Wrapper }
    );

    expect(screen.getByText('Test error message')).toBeInTheDocument();

    consoleSpy.mockRestore();
  });

  it('should display the error page title when an error occurs', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const testError = new Error('Something went wrong');

    render(
      <ErrorBoundary>
        <ThrowingComponent error={testError} />
      </ErrorBoundary>,
      { wrapper: Wrapper }
    );

    expect(screen.getByText('Application Stopped Working')).toBeInTheDocument();

    consoleSpy.mockRestore();
  });
});
