/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { setupReactRouterMock } from 'tests/mocks';
import { vi } from 'vitest';

setupReactRouterMock();

import CustomButton from './CustomButton';

describe('CustomButton', () => {
  afterAll(() => vi.resetModules());

  describe('rendering', () => {
    it('renders a button element', () => {
      render(<CustomButton>Click me</CustomButton>);
      expect(screen.getByRole('button', { name: 'Click me' })).toBeInTheDocument();
    });

    it('renders with MUI Button classes', () => {
      render(<CustomButton>Test</CustomButton>);
      expect(screen.getByRole('button')).toHaveClass('MuiButton-root');
    });

    it('renders children text', () => {
      render(<CustomButton>My Button</CustomButton>);
      expect(screen.getByText('My Button')).toBeInTheDocument();
    });
  });

  describe('variants', () => {
    it('renders contained variant', () => {
      render(<CustomButton variant="contained">Contained</CustomButton>);
      expect(screen.getByRole('button')).toHaveClass('MuiButton-contained');
    });

    it('renders outlined variant', () => {
      render(<CustomButton variant="outlined">Outlined</CustomButton>);
      expect(screen.getByRole('button')).toHaveClass('MuiButton-outlined');
    });

    it('renders text variant', () => {
      render(<CustomButton variant="text">Text</CustomButton>);
      expect(screen.getByRole('button')).toHaveClass('MuiButton-text');
    });
  });

  describe('MUI color prop', () => {
    it('renders with primary color by default', () => {
      render(<CustomButton>Primary</CustomButton>);
      expect(screen.getByRole('button')).toHaveClass('MuiButton-colorPrimary');
    });

    it('renders with secondary color', () => {
      render(<CustomButton color="secondary">Secondary</CustomButton>);
      expect(screen.getByRole('button')).toHaveClass('MuiButton-colorSecondary');
    });

    it('renders with error color', () => {
      render(<CustomButton color="error">Error</CustomButton>);
      expect(screen.getByRole('button')).toHaveClass('MuiButton-colorError');
    });

    it('renders with inherit color for custom hex colors', () => {
      render(<CustomButton color="#ff0000">Custom</CustomButton>);
      expect(screen.getByRole('button')).toHaveClass('MuiButton-colorInherit');
    });
  });

  describe('progress', () => {
    it('shows a progress indicator when progress is true', () => {
      render(<CustomButton progress>Loading</CustomButton>);
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    it('does not show a progress indicator when progress is false', () => {
      render(<CustomButton progress={false}>Not Loading</CustomButton>);
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    });
  });

  describe('tooltip', () => {
    it('wraps button in a tooltip when tooltip prop is provided', () => {
      render(<CustomButton tooltip="Help text">Hover me</CustomButton>);
      // Tooltip wraps in a span
      const button = screen.getByRole('button');
      expect(button.closest('span')).toBeInTheDocument();
    });
  });

  describe('routing', () => {
    it('wraps button in a Link when route prop is provided', () => {
      render(<CustomButton route="/test-route">Navigate</CustomButton>);
      const link = screen.getByRole('link');
      expect(link).toHaveAttribute('href', '/test-route');
    });

    it('wraps button in an anchor tag when href prop is provided', () => {
      render(<CustomButton href="https://example.com">External</CustomButton>);
      const link = screen.getByRole('link');
      expect(link).toHaveAttribute('href', 'https://example.com');
    });

    it('does not wrap button in link when neither route nor href is provided', () => {
      render(<CustomButton>Plain</CustomButton>);
      expect(screen.queryByRole('link')).not.toBeInTheDocument();
    });
  });

  describe('disabled state', () => {
    it('renders disabled button when disabled prop is true', () => {
      render(<CustomButton disabled>Disabled</CustomButton>);
      expect(screen.getByRole('button')).toBeDisabled();
    });
  });

  describe('sizes', () => {
    it('renders small size', () => {
      render(<CustomButton size="small">Small</CustomButton>);
      expect(screen.getByRole('button')).toHaveClass('MuiButton-sizeSmall');
    });

    it('renders large size', () => {
      render(<CustomButton size="large">Large</CustomButton>);
      expect(screen.getByRole('button')).toHaveClass('MuiButton-sizeLarge');
    });
  });
});
