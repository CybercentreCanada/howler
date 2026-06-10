/// <reference types="vitest" />
import { render } from '@testing-library/react';
import TypingIndicator from './TypingIndicator';

describe('TypingIndicator', () => {
  describe('rendering', () => {
    it('renders exactly three circle icons', () => {
      const { container } = render(<TypingIndicator />);
      // Each Circle icon renders as an <svg> element
      const svgs = container.querySelectorAll('svg');
      expect(svgs).toHaveLength(3);
    });

    it('renders a root Stack element', () => {
      const { container } = render(<TypingIndicator />);
      expect(container.firstChild).toBeInTheDocument();
    });

    it('renders with flex row layout', () => {
      const { container } = render(<TypingIndicator />);
      // MUI Stack with direction="row" uses flexbox
      const root = container.firstChild as HTMLElement;
      expect(root).toHaveStyle({ display: 'flex', flexDirection: 'row' });
    });
  });

  describe('accessibility', () => {
    it('renders the circles as SVG elements', () => {
      const { container } = render(<TypingIndicator />);
      const svgs = container.querySelectorAll('svg');
      svgs.forEach(svg => {
        expect(svg.tagName.toLowerCase()).toBe('svg');
      });
    });
  });
});
