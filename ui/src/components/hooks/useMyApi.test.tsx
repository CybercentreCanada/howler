/// <reference types="vitest" />
import { renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const mockShowErrorMessage = vi.hoisted(() => vi.fn());

vi.mock('./useMySnackbar', () => ({
  default: () => ({ showErrorMessage: mockShowErrorMessage })
}));

import useMyApi from './useMyApi';

describe('useMyApi', () => {
  it('returns successful API responses', async () => {
    const { result } = renderHook(() => useMyApi());
    await expect(result.current.dispatchApi(Promise.resolve('ok'))).resolves.toBe('ok');
  });

  it('handles conflicts through the callback without surfacing an error', async () => {
    const { result } = renderHook(() => useMyApi());
    const onConflict = vi.fn();
    const error = Object.assign(new Error('conflict'), { cause: { api_status_code: 409 } });

    await expect(result.current.dispatchApi(Promise.reject(error), { onConflict })).resolves.toBeUndefined();
    expect(onConflict).toHaveBeenCalled();
    expect(mockShowErrorMessage).not.toHaveBeenCalled();
  });

  it('shows, logs, and rethrows errors according to config', async () => {
    const { result } = renderHook(() => useMyApi());
    const error = new Error('failed');
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined);

    await expect(result.current.dispatchApi(Promise.reject(error), { logError: true })).rejects.toThrow('failed');
    expect(mockShowErrorMessage).toHaveBeenCalledWith('failed');
    expect(consoleSpy).toHaveBeenCalledWith(error);

    await expect(
      result.current.dispatchApi(Promise.reject(error), { throwError: false, showError: false, logError: false })
    ).resolves.toBeUndefined();
  });
});
