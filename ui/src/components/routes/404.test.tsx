import { render, screen } from '@testing-library/react';
import i18n from 'i18n';
import { I18nextProvider } from 'react-i18next';
import { describe, expect, it, vi } from 'vitest';
import NotFoundPage from './404';

vi.mock('commons/components/pages/PageCenter', () => ({
  default: ({ children }: { children: React.ReactNode }) => <div id="page-center">{children}</div>
}));

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <I18nextProvider i18n={i18n as any}>{children}</I18nextProvider>
);

describe('NotFoundPage (404)', () => {
  it('should render the 404 title and description', () => {
    render(<NotFoundPage />, { wrapper: Wrapper });

    expect(screen.getByText('404: Not found')).toBeInTheDocument();
    expect(screen.getByText('The page you are looking for cannot be found...')).toBeInTheDocument();
  });

  it('should render inside PageCenter', () => {
    render(<NotFoundPage />, { wrapper: Wrapper });

    expect(screen.getByTestId('page-center')).toBeInTheDocument();
  });

  it('should render the LinkOff icon', () => {
    render(<NotFoundPage />, { wrapper: Wrapper });

    expect(document.querySelector('[data-testid="LinkOffIcon"]')).toBeInTheDocument();
  });
});
