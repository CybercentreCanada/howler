/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const mockExecuteFunction = vi.hoisted(() => vi.fn());

vi.mock('plugins/store', () => ({
  default: { plugins: ['one', 'two', 'three'] }
}));

vi.mock('react-pluggable', () => ({
  usePluginStore: () => ({ executeFunction: mockExecuteFunction })
}));

import CustomPluginProvider from './CustomPluginProvider';

describe('CustomPluginProvider', () => {
  it('wraps children with every plugin provider returned by the store', () => {
    mockExecuteFunction.mockImplementation((key: string) => {
      if (key === 'one.provider') return ({ children }: any) => <div>one:{children}</div>;
      if (key === 'two.provider') return undefined;
      if (key === 'three.provider') return ({ children }: any) => <div>three:{children}</div>;
      return undefined;
    });

    render(
      <CustomPluginProvider>
        <span>child</span>
      </CustomPluginProvider>
    );

    expect(screen.getByText('three:')).toBeInTheDocument();
    expect(screen.getByText('one:')).toBeInTheDocument();
    expect(screen.getByText('child')).toBeInTheDocument();
  });
});
