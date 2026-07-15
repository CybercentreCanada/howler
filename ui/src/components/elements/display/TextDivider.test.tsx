/// <reference types="vitest" />
import { render } from '@testing-library/react';
import i18n from 'i18n';
import { I18nextProvider } from 'react-i18next';
import TextDivider from './TextDivider';

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <I18nextProvider i18n={i18n as any}>{children}</I18nextProvider>
);

describe('TextDivider', () => {
  describe('rendering', () => {
    it('renders without crashing', () => {
      const { container } = render(<TextDivider />, { wrapper: Wrapper });
      expect(container.firstChild).toBeInTheDocument();
    });

    it('renders with inline-block display style', () => {
      const { container } = render(<TextDivider />, { wrapper: Wrapper });
      expect(container.firstChild).toHaveStyle({ display: 'inline-block' });
    });

    it('renders with text-align center', () => {
      const { container } = render(<TextDivider />, { wrapper: Wrapper });
      expect(container.firstChild).toHaveStyle({ textAlign: 'center' });
    });

    it('renders with width 100%', () => {
      const { container } = render(<TextDivider />, { wrapper: Wrapper });
      expect(container.firstChild).toHaveStyle({ width: '100%' });
    });

    it('renders with position relative', () => {
      const { container } = render(<TextDivider />, { wrapper: Wrapper });
      expect(container.firstChild).toHaveStyle({ position: 'relative' });
    });

    it('renders a nested div element', () => {
      const { container } = render(<TextDivider />, { wrapper: Wrapper });
      const outerDiv = container.firstChild as HTMLElement;
      expect(outerDiv.querySelector('div')).toBeInTheDocument();
    });

    it('renders the translated divider text', () => {
      const { container } = render(<TextDivider />, { wrapper: Wrapper });
      // The divider uses i18n key 'divider', text should be present
      const innerDiv = container.querySelector('div > div');
      expect(innerDiv).toBeInTheDocument();
      expect(innerDiv.textContent).toBeTruthy();
    });
  });
});
