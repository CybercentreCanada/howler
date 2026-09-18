/// <reference types="vitest" />
import { renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const mockEnqueueSnackbar = vi.hoisted(() => vi.fn());
const mockCloseSnackbar = vi.hoisted(() => vi.fn());

vi.mock('notistack', () => ({
  useSnackbar: () => ({
    enqueueSnackbar: mockEnqueueSnackbar,
    closeSnackbar: mockCloseSnackbar
  })
}));

import useMySnackbar from './useMySnackbar';

describe('useMySnackbar', () => {
  it('enqueues typed snackbar messages with default options', () => {
    const { result } = renderHook(() => useMySnackbar());

    result.current.showSuccessMessage('saved');
    result.current.showWarningMessage('warn', 2000);
    result.current.showErrorMessage('error');
    result.current.showInfoMessage('info');

    expect(mockEnqueueSnackbar).toHaveBeenCalledWith(
      'saved',
      expect.objectContaining({
        variant: 'success',
        autoHideDuration: 5000,
        preventDuplicate: true
      })
    );
    expect(mockEnqueueSnackbar).toHaveBeenCalledWith('warn', expect.objectContaining({ variant: 'warning', autoHideDuration: 2000 }));
  });

  it('merges custom snackbar click handlers with the default close handler', () => {
    const { result } = renderHook(() => useMySnackbar());
    const onClick = vi.fn();

    result.current.showInfoMessage('custom', 1000, { SnackbarProps: { onClick } });

    const options = mockEnqueueSnackbar.mock.calls.at(-1)![1];
    options.SnackbarProps.onClick('event');
    expect(onClick).toHaveBeenCalledWith('event');
    expect(mockCloseSnackbar).toHaveBeenCalled();
  });
});
