/// <reference types="vitest" />
import { act, render, screen } from '@testing-library/react';
import i18n from 'i18n';
import React from 'react';
import { I18nextProvider } from 'react-i18next';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ViewRefresh, { type ViewRefreshHandle } from './ViewRefresh';

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <I18nextProvider i18n={i18n as any}>{children}</I18nextProvider>
);

const createRefs = (refreshRate = 30, viewCardIds = ['one', 'two']) => ({
  refreshRateRef: { current: refreshRate },
  viewCardIdsRef: { current: viewCardIds }
});

describe('ViewRefresh', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should render the refresh button', () => {
    render(<ViewRefresh {...createRefs()} onRefresh={vi.fn()} />, { wrapper: Wrapper });

    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('should show a progress indicator initially', () => {
    render(<ViewRefresh {...createRefs()} onRefresh={vi.fn()} />, { wrapper: Wrapper });

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('reschedules the countdown using an updated refresh rate', () => {
    const ref = React.createRef<ViewRefreshHandle>();
    const refs = createRefs(30);

    render(<ViewRefresh ref={ref} {...refs} onRefresh={vi.fn()} />, { wrapper: Wrapper });

    const progress = screen.getByRole('progressbar');
    expect(progress).toHaveAttribute('aria-valuenow', '0');

    act(() => {
      refs.refreshRateRef.current = 60;
      ref.current?.updateRefreshRate();
    });

    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(progress).toHaveAttribute('aria-valuenow', '0');

    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(progress).toHaveAttribute('aria-valuenow', '1');
  });

  it('should trigger refresh when progress reaches 100%', async () => {
    const onRefresh = vi.fn();

    render(<ViewRefresh {...createRefs()} onRefresh={onRefresh} />, { wrapper: Wrapper });

    // Progress increments by 1 every refreshRate*10ms = 300ms.
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

    render(<ViewRefresh ref={ref} {...createRefs()} onRefresh={onRefresh} />, { wrapper: Wrapper });

    for (let i = 0; i < 101; i++) {
      await act(async () => {
        vi.advanceTimersByTime(300);
      });
    }

    expect(onRefresh).toHaveBeenCalled();

    act(() => {
      ref.current?.handleRefreshComplete('one', onRefresh.mock.calls[0][0]);
      ref.current?.handleRefreshComplete('two', onRefresh.mock.calls[0][0]);
    });

    expect(screen.getByRole('button')).not.toBeDisabled();
  });

  it('should trigger refresh via manual click', () => {
    const onRefresh = vi.fn();

    render(<ViewRefresh {...createRefs()} onRefresh={onRefresh} />, { wrapper: Wrapper });

    act(() => {
      screen.getByRole('button').click();
    });

    expect(onRefresh).toHaveBeenCalled();
  });

  it('should not call onRefresh when there are no refreshable panels and the button is clicked', () => {
    const onRefresh = vi.fn();

    render(<ViewRefresh {...createRefs(30, [])} onRefresh={onRefresh} />, { wrapper: Wrapper });

    act(() => {
      screen.getByRole('button').click();
    });

    expect(onRefresh).not.toHaveBeenCalled();
  });

  it('keeps active refresh tracking in sync with dashboard panel edits', () => {
    const onRefresh = vi.fn();
    const ref = React.createRef<ViewRefreshHandle>();
    const refs = createRefs();

    render(<ViewRefresh ref={ref} {...refs} onRefresh={onRefresh} />, { wrapper: Wrapper });

    act(() => {
      screen.getByRole('button').click();
    });

    const refreshTick = onRefresh.mock.calls[0][0];
    act(() => {
      refs.viewCardIdsRef.current = ['one', 'two', 'three'];
      ref.current?.updateViewCardIds(refs.viewCardIdsRef.current);
      ref.current?.handleRefreshComplete('one', refreshTick);
      ref.current?.handleRefreshComplete('two', refreshTick);
    });

    expect(screen.getByRole('button')).toBeDisabled();

    act(() => {
      ref.current?.handleRefreshComplete('three', refreshTick);
    });
    expect(screen.getByRole('button')).not.toBeDisabled();
  });

  it('ends an active refresh when dashboard edits remove all pending panels', () => {
    const onRefresh = vi.fn();
    const ref = React.createRef<ViewRefreshHandle>();
    const refs = createRefs();

    render(<ViewRefresh ref={ref} {...refs} onRefresh={onRefresh} />, { wrapper: Wrapper });

    act(() => {
      screen.getByRole('button').click();
    });

    act(() => {
      refs.viewCardIdsRef.current = [];
      ref.current?.updateViewCardIds(refs.viewCardIdsRef.current);
    });

    expect(screen.getByRole('button')).not.toBeDisabled();
  });
});
