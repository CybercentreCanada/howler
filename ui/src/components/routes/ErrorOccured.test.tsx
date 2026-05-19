/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import type * as TuiCore from '@tui/core';
import i18n from 'i18n';
import { I18nextProvider } from 'react-i18next';
import { describe, expect, it, vi } from 'vitest';
import ErrorOccured from './ErrorOccured';

vi.mock('@tui/core', async () => {
  const actual = await vi.importActual<typeof TuiCore>('@tui/core');
  return {
    ...actual,
    PageCenter: ({ children }: { children: React.ReactNode }) => <div id="page-center">{children}</div>
  };
});

const mockExecuteFunction = vi.fn(() => null);
vi.mock('react-pluggable', () => ({
  usePluginStore: () => ({
    executeFunction: mockExecuteFunction
  })
}));

vi.mock('plugins/store', () => ({
  default: { plugins: ['TestPlugin'] }
}));

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <I18nextProvider i18n={i18n as any}>{children}</I18nextProvider>
);

describe('ErrorOccured', () => {
  it('should render the error title and description', () => {
    render(<ErrorOccured />, { wrapper: Wrapper });

    expect(screen.getByText('Application Stopped Working')).toBeInTheDocument();
    expect(
      screen.getByText('The application stopped working suddenly. If the problem persists please reach out on teams.')
    ).toBeInTheDocument();
  });

  it('should render inside PageCenter', () => {
    render(<ErrorOccured />, { wrapper: Wrapper });

    expect(screen.getByTestId('page-center')).toBeInTheDocument();
  });

  it('should execute plugin support functions', () => {
    render(<ErrorOccured />, { wrapper: Wrapper });

    expect(mockExecuteFunction).toHaveBeenCalledWith('TestPlugin.support');
  });
});
