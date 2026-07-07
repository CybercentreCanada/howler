/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { setupReactRouterMock } from 'tests/mocks';
import { vi } from 'vitest';

setupReactRouterMock();

import CustomIconButton from './CustomIconButton';

describe('CustomIconButton', () => {
  afterAll(() => vi.resetModules());

  describe('rendering', () => {
    it('renders a button element', () => {
      render(<CustomIconButton aria-label="test">icon</CustomIconButton>);
      expect(screen.getByRole('button', { name: 'test' })).toBeInTheDocument();
    });

    it('renders children inside the button', () => {
      render(<CustomIconButton>★</CustomIconButton>);
      expect(screen.getByText('★')).toBeInTheDocument();
    });

    it('renders with MUI IconButton classes', () => {
      render(<CustomIconButton>i</CustomIconButton>);
      expect(screen.getByRole('button')).toHaveClass('MuiIconButton-root');
    });
  });

  describe('disabled state', () => {
    it('is disabled when disabled prop is true', () => {
      render(<CustomIconButton disabled>icon</CustomIconButton>);
      expect(screen.getByRole('button')).toBeDisabled();
    });

    it('is disabled when progress is truthy', () => {
      render(<CustomIconButton progress>icon</CustomIconButton>);
      expect(screen.getByRole('button')).toBeDisabled();
    });

    it('is NOT disabled when progress is set but clickableWithProgress=true', () => {
      render(
        <CustomIconButton progress clickableWithProgress>
          icon
        </CustomIconButton>
      );
      expect(screen.getByRole('button')).not.toBeDisabled();
    });
  });

  describe('progress indicator', () => {
    it('renders a CircularProgress when progress is truthy', () => {
      render(<CustomIconButton progress>icon</CustomIconButton>);
      // CircularProgress renders an svg with role="progressbar"
      expect(document.querySelector('circle')).toBeInTheDocument();
    });

    it('does not render CircularProgress when progress is falsy', () => {
      render(<CustomIconButton>icon</CustomIconButton>);
      expect(document.querySelector('[role="progressbar"]')).not.toBeInTheDocument();
    });
  });

  describe('tooltip', () => {
    it('wraps the button in a Tooltip when tooltip prop is provided', () => {
      render(<CustomIconButton tooltip="Save">icon</CustomIconButton>);
      // The button is wrapped in a <span> when a Tooltip is used
      const span = screen.getByRole('button').closest('span');
      expect(span).toBeInTheDocument();
    });

    it('does not add a surrounding span when no tooltip is given', () => {
      render(<CustomIconButton>icon</CustomIconButton>);
      const button = screen.getByRole('button');
      // Without tooltip the immediate parent should NOT be a span wrapper
      expect(button.parentElement?.tagName).not.toBe('SPAN');
    });
  });

  describe('route link', () => {
    it('wraps the button in a Link when route prop is provided', () => {
      render(<CustomIconButton route="/hits">icon</CustomIconButton>);
      expect(screen.getByRole('link')).toBeInTheDocument();
    });

    it('does not render a link when no route is given', () => {
      render(<CustomIconButton>icon</CustomIconButton>);
      expect(screen.queryByRole('link')).not.toBeInTheDocument();
    });
  });

  describe('href link', () => {
    it('wraps the button in an anchor tag when href is provided', () => {
      render(<CustomIconButton href="https://example.com">icon</CustomIconButton>);
      const anchor = screen.getByRole('link');
      expect(anchor).toBeInTheDocument();
      expect(anchor).toHaveAttribute('href', 'https://example.com');
    });
  });
});
