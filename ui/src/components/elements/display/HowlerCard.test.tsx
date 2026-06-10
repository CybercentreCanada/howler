/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import HowlerCard from './HowlerCard';

describe('HowlerCard', () => {
  describe('rendering', () => {
    it('renders children', () => {
      render(
        <HowlerCard>
          <div id="child">content</div>
        </HowlerCard>
      );
      expect(screen.getByTestId('child')).toBeInTheDocument();
    });

    it('renders as a MUI Card', () => {
      const { container } = render(<HowlerCard />);
      expect(container.firstChild).toHaveClass('MuiCard-root');
    });

    it('always applies outline: none style', () => {
      const { container } = render(<HowlerCard />);
      expect(container.firstChild).toHaveStyle({ outline: 'none' });
    });
  });

  describe('elevation', () => {
    it('uses elevation 4 when no variant is specified', () => {
      const { container } = render(<HowlerCard />);
      expect(container.firstChild).toHaveClass('MuiPaper-elevation4');
    });

    it('uses elevation 4 when variant is not outlined', () => {
      const { container } = render(<HowlerCard variant="elevation" />);
      expect(container.firstChild).toHaveClass('MuiPaper-elevation4');
    });

    it('uses the outlined variant style (not elevation) when variant is outlined', () => {
      const { container } = render(<HowlerCard variant="outlined" />);
      // MUI renders the outlined variant with MuiPaper-outlined, not an elevation class
      expect(container.firstChild).toHaveClass('MuiPaper-outlined');
      expect(container.firstChild).not.toHaveClass('MuiPaper-elevation4');
    });
  });

  describe('prop passthrough', () => {
    it('passes id to the underlying Card', () => {
      render(<HowlerCard id="my-card" />);
      expect(screen.getByTestId('my-card')).toBeInTheDocument();
    });

    it('passes className to the underlying Card', () => {
      const { container } = render(<HowlerCard className="custom-class" />);
      expect(container.firstChild).toHaveClass('custom-class');
    });

    it('passes custom sx styles', () => {
      const { container } = render(<HowlerCard sx={{ color: 'red' }} />);
      expect(container.firstChild).toHaveStyle({ color: 'rgb(255, 0, 0)' });
    });

    it('allows a custom elevation override', () => {
      const { container } = render(<HowlerCard elevation={8} />);
      // elevation prop spreads after the default, overriding it
      expect(container.firstChild).toHaveClass('MuiPaper-elevation8');
    });
  });
});
