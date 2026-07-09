import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import FlexVertical from './FlexVertical';

describe('FlexVertical', () => {
  it('renders a div with display:flex and flex-direction:column', () => {
    const { container } = render(
      <FlexVertical>
        <span>child</span>
      </FlexVertical>
    );
    const div = container.firstChild as HTMLElement;
    expect(div).toBeInTheDocument();
    expect(div).toHaveStyle({ display: 'flex', flexDirection: 'column' });
  });

  it('renders children inside the flex container', () => {
    render(
      <FlexVertical>
        <span id="inner">hello</span>
      </FlexVertical>
    );
    expect(screen.getByTestId('inner')).toBeInTheDocument();
  });

  it('renders multiple children', () => {
    render(
      <FlexVertical>
        <span id="a">A</span>
        <span id="b">B</span>
      </FlexVertical>
    );
    expect(screen.getByTestId('a')).toBeInTheDocument();
    expect(screen.getByTestId('b')).toBeInTheDocument();
  });

  it('applies the default flex value of 1', () => {
    const { container } = render(
      <FlexVertical>
        <span>child</span>
      </FlexVertical>
    );
    const div = container.firstChild as HTMLElement;
    expect(div).toHaveStyle({ flex: 1 });
  });

  it('applies a custom flex value when provided', () => {
    const { container } = render(
      <FlexVertical flex={2}>
        <span>child</span>
      </FlexVertical>
    );
    const div = container.firstChild as HTMLElement;
    expect(div).toHaveStyle({ flex: 2 });
  });
});
