/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { setupReactRouterMock } from 'tests/mocks';
import { vi } from 'vitest';

setupReactRouterMock();

import i18n from 'i18n';
import { I18nextProvider } from 'react-i18next';
import QueryResultText from './QueryResultText';

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <I18nextProvider i18n={i18n as any}>{children}</I18nextProvider>
);

describe('QueryResultText', () => {
  afterAll(() => vi.resetModules());

  describe('rendering', () => {
    it('renders a Typography element', () => {
      const { container } = render(<QueryResultText count={5} query="howler.status:open" />, { wrapper: Wrapper });
      expect(container.querySelector('.MuiTypography-root')).toBeInTheDocument();
    });

    it('renders with body2 variant', () => {
      const { container } = render(<QueryResultText count={5} query="howler.status:open" />, { wrapper: Wrapper });
      expect(container.firstChild).toHaveClass('MuiTypography-body2');
    });

    it('renders a link element', () => {
      render(<QueryResultText count={5} query="howler.status:open" />, { wrapper: Wrapper });
      expect(screen.getByRole('link')).toBeInTheDocument();
    });

    it('encodes the query in the link href', () => {
      render(<QueryResultText count={5} query="howler.status:open AND howler.id:*" />, { wrapper: Wrapper });
      const link = screen.getByRole('link');
      expect(link).toHaveAttribute('href', '/hits?query=howler.status%3Aopen%20AND%20howler.id%3A*');
    });

    it('handles special characters in query', () => {
      render(<QueryResultText count={1} query='howler.detection:"test & value"' />, { wrapper: Wrapper });
      const link = screen.getByRole('link');
      expect(link.getAttribute('href')).toContain('/hits?query=');
      expect(link.getAttribute('href')).toContain(encodeURIComponent('howler.detection:"test & value"'));
    });
  });

  describe('count display', () => {
    it('displays the count value', () => {
      render(<QueryResultText count={42} query="test" />, { wrapper: Wrapper });
      expect(screen.getByText(/42/)).toBeInTheDocument();
    });

    it('displays zero count', () => {
      render(<QueryResultText count={0} query="test" />, { wrapper: Wrapper });
      expect(screen.getByText(/0/)).toBeInTheDocument();
    });
  });
});
