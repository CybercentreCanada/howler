/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

let mode: 'light' | 'dark' = 'light';

vi.mock('@mui/material', () => ({
  Stack: ({ children, direction, alignItems, style }: any) => (
    <div data-direction={direction} data-align-items={alignItems} data-style={JSON.stringify(style)}>
      {children}
    </div>
  ),
  useTheme: () => ({ palette: { mode } })
}));

import { AppBrand, SIZES } from './AppBrand';

describe('AppBrand', () => {
  it('renders a logo-only variant', () => {
    render(<AppBrand application="howler" variant="logo" size="small" />);

    const logo = screen.getByAltText('howler logo');
    expect(logo).toHaveAttribute('src', '/branding/howler/noswoosh-light.svg');
    expect(logo).toHaveStyle({ width: `${SIZES.small.icon.width}px`, height: `${SIZES.small.icon.height}px` });
    expect(screen.queryByAltText('howler')).not.toBeInTheDocument();
  });

  it('renders app and banner variants with the themed name asset', () => {
    mode = 'dark';
    const { rerender, container } = render(<AppBrand application="assemblyline" variant="app" size="medium" />);

    expect(screen.getByAltText('assemblyline logo')).toHaveAttribute('src', '/branding/assemblyline/noswoosh-dark.svg');
    expect(screen.getByAltText('assemblyline')).toHaveAttribute('src', '/branding/assemblyline/name-dark.svg');
    expect(container.firstChild).toHaveAttribute('data-direction', 'row');

    rerender(<AppBrand application="analyticalplatform" variant="banner-vertical" size="xsmall" />);
    expect(container.firstChild).toHaveAttribute('data-direction', 'column');
    expect(screen.getByAltText('analyticalplatform')).toHaveAttribute('src', '/branding/analyticalplatform/name-dark.svg');
  });
});
