/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const apiConfigContextToken = vi.hoisted(() => ({ name: 'api-config-context' }));
let configValue: any = {
  config: {
    c12nDef: {
      levels_map: { 0: 'secret' },
      levels_styles_map: { secret: { color: 'primary' } }
    }
  }
};

const mockGetParts = vi.hoisted(() => vi.fn(() => ({ lvlIdx: 0 })));
const mockNormalized = vi.hoisted(() => vi.fn(() => 'S'));

vi.mock('@mui/material', () => ({
  Chip: ({ label, color, sx, variant }: any) => <div data-color={color} data-variant={variant} data-sx={JSON.stringify(sx)}>{label}</div>,
  Tooltip: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/app/providers/ApiConfigProvider', () => ({
  ApiConfigContext: apiConfigContextToken
}));

vi.mock('utils/classificationParser', () => ({
  getParts: mockGetParts,
  normalizedClassification: mockNormalized
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === apiConfigContextToken) return configValue;
      return actual.useContext(context);
    }
  };
});

import ClassificationChip from './ClassificationChip';

describe('ClassificationChip', () => {
  it('renders normalized values with theme colors', () => {
    render(<ClassificationChip classification="SECRET" />);
    expect(screen.getByText('S')).toHaveAttribute('data-color', 'primary');
  });

  it('falls back to sx colors or the original classification', () => {
    configValue = {
      config: {
        c12nDef: {
          levels_map: { 0: 'secret' },
          levels_styles_map: { secret: { color: '#ff0000' } }
        }
      }
    };
    const { rerender } = render(<ClassificationChip classification="SECRET" variant="filled" sx={{ m: 1 }} />);
    expect(screen.getByText('S')).toHaveAttribute('data-variant', 'filled');
    expect(screen.getByText('S').getAttribute('data-sx')).toContain('#ff0000');

    configValue = { config: { c12nDef: undefined } };
    rerender(<ClassificationChip classification="RAW" />);
    expect(screen.getByText('RAW')).toHaveAttribute('data-color', 'default');
  });
});
