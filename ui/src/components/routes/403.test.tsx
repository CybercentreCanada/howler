import { render, screen } from '@testing-library/react';
import i18n from 'i18n';
import { I18nextProvider } from 'react-i18next';
import { describe, expect, it, vi } from 'vitest';
import PermissionDeniedPage from './403';

vi.mock('commons/components/pages/PageCenter', () => ({
  default: ({ children }: { children: React.ReactNode }) => <div id="page-center">{children}</div>
}));

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <I18nextProvider i18n={i18n as any}>{children}</I18nextProvider>
);

describe('PermissionDeniedPage (403)', () => {
  it('should render the 403 title and description', () => {
    render(<PermissionDeniedPage />, { wrapper: Wrapper });

    expect(screen.getByText('403: Access Forbidden')).toBeInTheDocument();
    expect(screen.getByText('You do not have permission to access this page.')).toBeInTheDocument();
  });

  it('should render inside PageCenter', () => {
    render(<PermissionDeniedPage />, { wrapper: Wrapper });

    expect(screen.getByTestId('page-center')).toBeInTheDocument();
  });

  it('should render the PersonOff icon', () => {
    render(<PermissionDeniedPage />, { wrapper: Wrapper });

    // MUI SVG icons have data-testid attribute
    expect(document.querySelector('[data-testid="PersonOffIcon"]')).toBeInTheDocument();
  });
});
