/// <reference types="vitest" />
import { act, render, screen } from '@testing-library/react';
import { useContext } from 'react';
import { describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());

vi.mock('api', () => ({
  default: { search: { fields: { hit: { get: () => ({}) } } } }
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

import FieldProvider, { FieldContext } from './FieldProvider';

const Consumer = () => {
  const ctx = useContext(FieldContext);
  return (
    <div>
      <button onClick={() => void ctx.getHitFields()}>load</button>
      <span>{ctx.hitFields.length}</span>
    </div>
  );
};

describe('FieldProvider', () => {
  it('loads hit fields once and reuses the cached value', async () => {
    mockDispatchApi.mockResolvedValue([{ name: 'field-a' }]);
    render(
      <FieldProvider>
        <Consumer />
      </FieldProvider>
    );

    await act(async () => screen.getByText('load').click());
    expect(mockDispatchApi).toHaveBeenCalledTimes(1);
    expect(screen.getByText('1')).toBeInTheDocument();

    await act(async () => screen.getByText('load').click());
    expect(mockDispatchApi).toHaveBeenCalledTimes(1);
  });
});
