/// <reference types="vitest" />
import { render, screen, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import i18n from 'i18n';
import React from 'react';
import { I18nextProvider } from 'react-i18next';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ViewRefresh, { type ViewRefreshHandle } from './ViewRefresh';

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <I18nextProvider i18n={i18n as any}>{children}</I18nextProvider>
);

describe('ViewRefresh', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should render the refresh button', () => {
    const onRefresh = vi.fn();

    render(<ViewRefresh refreshRate={30} viewCardCount={2} onRefresh={onRefresh} />, { wrapper: Wrapper });

    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('should show a progress indicator initially', () => {
    const onRefresh = vi.fn();

    render(<ViewRefresh refreshRate={30} viewCardCount={2} onRefresh={onRefresh} />, { wrapper: Wrapper });

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('should trigger refresh when progress reaches 100%', async () => {
    const onRefresh = vi.fn();

    render(<ViewRefresh refreshRate={30} viewCardCount={2} onRefresh={onRefresh} />, { wrapper: Wrapper });

    // Progress increments by 1 every refreshRate*10ms = 300ms.
    // Each increment triggers a re-render and a new setTimeout.
    // We advance one tick at a time inside act to let React process each state update.
    for (let i = 0; i < 101; i++) {
      await act(async () => {
        vi.advanceTimersByTime(300);
      });
    }

    expect(onRefresh).toHaveBeenCalled();
  });

  it('should clear refreshing state when all cards report back via ref', async () => {
    const onRefresh = vi.fn();
    const ref = React.createRef<ViewRefreshHandle>();

    render(<ViewRefresh ref={ref} refreshRate={30} viewCardCount={2} onRefresh={onRefresh} />, { wrapper: Wrapper });

    // Advance to 100% to trigger refresh
    for (let i = 0; i < 101; i++) {
      await act(async () => {
        vi.advanceTimersByTime(300);
      });
    }

    expect(onRefresh).toHaveBeenCalled();

    // Simulate both cards completing
    act(() => {
      ref.current?.handleRefreshComplete();
      ref.current?.handleRefreshComplete();
    });

    // After all cards complete, the progress should reset (button re-enabled)
    expect(screen.getByRole('button')).not.toBeDisabled();
  });

  it('should trigger refresh via manual click', () => {
    const onRefresh = vi.fn();

    render(<ViewRefresh refreshRate={30} viewCardCount={2} onRefresh={onRefresh} />, { wrapper: Wrapper });

    // Click the refresh button directly using fireEvent (avoids userEvent timer issues)
    const button = screen.getByRole('button');
    act(() => {
      button.click();
    });

    expect(onRefresh).toHaveBeenCalled();
  });

  it('should not call onRefresh when viewCardCount is 0 and button is clicked', () => {
    const onRefresh = vi.fn();

    render(<ViewRefresh refreshRate={30} viewCardCount={0} onRefresh={onRefresh} />, { wrapper: Wrapper });

    const button = screen.getByRole('button');
    act(() => {
      button.click();
    });

    // onRefresh should not be called because viewCardCount is 0
    expect(onRefresh).not.toHaveBeenCalled();
  });
});
