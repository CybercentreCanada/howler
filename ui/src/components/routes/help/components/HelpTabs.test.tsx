/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const mockUseMediaQuery = vi.hoisted(() => vi.fn());

vi.mock('@mui/material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/material')>();
  return {
    ...actual,
    useMediaQuery: mockUseMediaQuery
  };
});

import { Tab } from '@mui/material';
import HelpTabs from './HelpTabs';

describe('HelpTabs', () => {
  it('renders vertical tabs on wide screens', () => {
    mockUseMediaQuery.mockReturnValue(false);

    render(
      <HelpTabs value="one">
        <Tab label="One" value="one" />
      </HelpTabs>
    );

    expect(screen.getByRole('tablist')).toHaveAttribute('aria-orientation', 'vertical');
  });

  it('renders horizontal tabs on narrow screens', () => {
    mockUseMediaQuery.mockReturnValue(true);

    render(
      <HelpTabs value="one">
        <Tab label="One" value="one" />
      </HelpTabs>
    );

    expect(screen.getByRole('tablist')).not.toHaveAttribute('aria-orientation', 'vertical');
  });
});
