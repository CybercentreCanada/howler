/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('@tui/core', () => ({
  usePageProps: ({ props }: any) => ({
    className: 'page-class',
    style: {
      marginBottom: `${props.mb ?? 0}px`,
      marginLeft: `${props.ml ?? 0}px`,
      marginRight: `${props.mr ?? 0}px`,
      marginTop: `${props.mt ?? 0}px`
    }
  })
}));

import FlexPort from './FlexPort';

describe('FlexPort', () => {
  it('renders page props margins and default overflow', () => {
    render(
      <FlexPort id="content" mt={1} mr={2} mb={3} ml={4}>
        <div>child</div>
      </FlexPort>
    );

    const inner = screen.getByText('child').parentElement as HTMLElement;
    const outer = inner.parentElement as HTMLElement;
    expect(outer.className).toBe('page-class');
    expect(outer.style.marginTop).toBe('1px');
    expect(outer.style.marginRight).toBe('2px');
    expect(outer.style.marginBottom).toBe('3px');
    expect(outer.style.marginLeft).toBe('4px');
    expect(inner).toHaveAttribute('id', 'content');
    expect(inner.style.overflow).toBe('auto');
  });

  it('omits overflow when disableOverflow is true', () => {
    render(
      <FlexPort disableOverflow>
        <div>child</div>
      </FlexPort>
    );
    expect((screen.getByText('child').parentElement as HTMLElement).style.overflow).toBe('');
  });
});
