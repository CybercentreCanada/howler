/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import i18n from 'i18n';
import { I18nextProvider } from 'react-i18next';
import SearchTotal from './SearchTotal';

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <I18nextProvider i18n={i18n as any}>{children}</I18nextProvider>
);

describe('SearchTotal', () => {
  describe('rendering', () => {
    it('renders a Typography element', () => {
      const { container } = render(<SearchTotal total={10} offset={0} pageLength={10} />, { wrapper: Wrapper });
      expect(container.querySelector('.MuiTypography-root')).toBeInTheDocument();
    });

    it('renders "No results" text when total is 0', () => {
      render(<SearchTotal total={0} offset={0} pageLength={0} />, { wrapper: Wrapper });
      expect(screen.getByText('No results')).toBeInTheDocument();
    });

    it('renders "No results" text when total is 1', () => {
      render(<SearchTotal total={1} offset={0} pageLength={1} />, { wrapper: Wrapper });
      expect(screen.getByText('No results')).toBeInTheDocument();
    });

    it('renders range text when total is greater than 1', () => {
      render(<SearchTotal total={50} offset={0} pageLength={25} />, { wrapper: Wrapper });
      // "Showing 1 to 25 of 50 results"
      expect(screen.getByText(/Showing 1 to 25 of 50 results/)).toBeInTheDocument();
    });

    it('renders correct offset values', () => {
      render(<SearchTotal total={100} offset={25} pageLength={25} />, { wrapper: Wrapper });
      // Should show "Showing 26 to 50 of 100 results"
      expect(screen.getByText(/Showing 26 to 50 of 100 results/)).toBeInTheDocument();
    });
  });

  describe('prop passthrough', () => {
    it('passes className to Typography', () => {
      const { container } = render(<SearchTotal total={10} offset={0} pageLength={10} className="custom" />, {
        wrapper: Wrapper
      });
      expect(container.firstChild).toHaveClass('custom');
    });

    it('passes variant to Typography', () => {
      const { container } = render(
        <SearchTotal total={10} offset={0} pageLength={10} variant="caption" />,
        { wrapper: Wrapper }
      );
      expect(container.firstChild).toHaveClass('MuiTypography-caption');
    });
  });
});
