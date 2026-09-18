/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockExecuteFunction = vi.hoisted(() => vi.fn());

vi.mock('@mui/material', () => ({
  Chip: ({ children }: any) => <div>{`fallback:${children}`}</div>
}));

vi.mock('plugins/store', () => ({
  default: { plugins: ['plugin-a', 'plugin-b'] }
}));

vi.mock('react-pluggable', () => ({
  usePluginStore: () => ({ executeFunction: mockExecuteFunction })
}));

import PluginChip from './PluginChip';

describe('PluginChip', () => {
  beforeEach(() => {
    mockExecuteFunction.mockReset();
  });

  it('renders the first plugin-provided chip component', () => {
    mockExecuteFunction.mockImplementation((name: string) => (name === 'plugin-b.chip' ? <div>plugin-chip</div> : null));
    render(<PluginChip value="v" context="ctx">child</PluginChip>);
    expect(screen.getByText('plugin-chip')).toBeInTheDocument();
  });

  it('falls back to the default MUI chip when no plugin handles the value', () => {
    mockExecuteFunction.mockReturnValue(null);
    render(<PluginChip value="v" context="ctx">child</PluginChip>);
    expect(screen.getByText('fallback:child')).toBeInTheDocument();
  });
});
