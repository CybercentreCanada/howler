import { renderHook } from '@testing-library/react';
import type { PropsWithChildren } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  appUserReady: true,
  setReady: vi.fn(),
  snackbars: {
    showErrorMessage: vi.fn(),
    showInfoMessage: vi.fn(),
    showSuccessMessage: vi.fn(),
    showWarningMessage: vi.fn()
  }
}));

vi.mock('@tui/core', () => ({
  useAppUser: () => ({ isReady: () => mocks.appUserReady })
}));

vi.mock('@cccsaurora/clue-ui/data/event', () => ({
  SNACKBAR_EVENT_ID: 'clue.snackbar'
}));

vi.mock('@cccsaurora/clue-ui/hooks/useClue', () => ({
  default: () => ({ setReady: mocks.setReady })
}));

vi.mock('components/app/providers/ApiConfigProvider', async () => {
  const { createContext } = await import('react');
  return { ApiConfigContext: createContext({ config: {} }) };
});

vi.mock('components/hooks/useMySnackbar', () => ({
  default: () => mocks.snackbars
}));

import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import useSetup from './setup';

const setupWrapper =
  (config: object) =>
  ({ children }: PropsWithChildren) => (
    <ApiConfigContext.Provider value={{ config: config as never, setConfig: vi.fn(), loaded: true }}>
      {children}
    </ApiConfigContext.Provider>
  );

describe('Clue setup', () => {
  beforeEach(() => {
    mocks.appUserReady = true;
    mocks.setReady.mockReset();
    Object.values(mocks.snackbars).forEach(snackbar => snackbar.mockReset());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('routes snackbar events and removes the event listener on cleanup', () => {
    const { unmount } = renderHook(() => useSetup(), {
      wrapper: setupWrapper({ configuration: { features: { clue: true } } })
    });

    window.dispatchEvent(new CustomEvent('clue.snackbar', { detail: { level: 'success', message: 'done' } }));
    expect(mocks.snackbars.showSuccessMessage).toHaveBeenCalledWith('done', undefined, undefined);
    expect(mocks.setReady).toHaveBeenCalledWith(true);

    unmount();
    window.dispatchEvent(new CustomEvent('clue.snackbar', { detail: { level: 'error', message: 'ignored' } }));
    expect(mocks.snackbars.showErrorMessage).not.toHaveBeenCalled();
  });

  it('does not enable readiness for Borealis alone or before the app user is ready', () => {
    renderHook(() => useSetup(), {
      wrapper: setupWrapper({ configuration: { features: { borealis: true } } })
    });
    expect(mocks.setReady).not.toHaveBeenCalled();

    mocks.appUserReady = false;
    renderHook(() => useSetup(), {
      wrapper: setupWrapper({ configuration: { features: { clue: true } } })
    });
    expect(mocks.setReady).not.toHaveBeenCalled();
  });
});
