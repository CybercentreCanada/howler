import { render, screen } from '@testing-library/react';
import FlexOne from './FlexOne';

describe('FlexOne', () => {
  describe('rendering', () => {
    it('renders a div element', () => {
      const { container } = render(<FlexOne />);
      expect(container.querySelector('div')).toBeInTheDocument();
    });

    it('applies flex: 1 style', () => {
      const { container } = render(<FlexOne />);
      expect(container.firstChild).toHaveStyle({ flex: '1' });
    });

    it('renders children inside the div', () => {
      render(
        <FlexOne>
          <span id="inner">hello</span>
        </FlexOne>
      );
      expect(screen.getByTestId('inner')).toBeInTheDocument();
    });

    it('renders without children without error', () => {
      const { container } = render(<FlexOne />);
      expect(container.firstChild).toBeInTheDocument();
      expect(container.firstChild).toBeEmptyDOMElement();
    });

    it('renders multiple children', () => {
      render(
        <FlexOne>
          <span id="a">A</span>
          <span id="b">B</span>
        </FlexOne>
      );
      expect(screen.getByTestId('a')).toBeInTheDocument();
      expect(screen.getByTestId('b')).toBeInTheDocument();
    });
  });
});
