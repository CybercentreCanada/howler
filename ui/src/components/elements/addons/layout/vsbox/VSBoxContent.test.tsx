/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import VSBoxContent from './VSBoxContent';

describe('VSBoxContent', () => {
  it('renders children inside a div with data-vsbox-content attribute', () => {
    render(
      <VSBoxContent>
        <span>hello</span>
      </VSBoxContent>
    );
    const el = document.querySelector('[data-vsbox-content]');
    expect(el).toBeInTheDocument();
    expect(el).toHaveAttribute('data-vsbox-content', 'true');
  });

  it('renders children correctly', () => {
    render(
      <VSBoxContent>
        <span id="child">content</span>
      </VSBoxContent>
    );
    expect(screen.getByTestId('child')).toBeInTheDocument();
  });

  it('passes additional MUI Box props through', () => {
    const { container } = render(
      <VSBoxContent sx={{ display: 'flex' }}>
        <span>content</span>
      </VSBoxContent>
    );
    expect(container.firstChild).toBeInTheDocument();
  });

  it('renders multiple children', () => {
    render(
      <VSBoxContent>
        <span id="a">A</span>
        <span id="b">B</span>
      </VSBoxContent>
    );
    expect(screen.getByTestId('a')).toBeInTheDocument();
    expect(screen.getByTestId('b')).toBeInTheDocument();
  });
});
