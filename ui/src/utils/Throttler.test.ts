/// <reference types="vitest" />
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Throttler from './Throttler';

describe('Throttler', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // -------------------------------------------------------------------------
  // throttle
  // -------------------------------------------------------------------------
  describe('throttle', () => {
    it('calls fn immediately on the first invocation', () => {
      const fn = vi.fn();
      const t = new Throttler(100);
      t.throttle(fn);
      expect(fn).toHaveBeenCalledTimes(1);
    });

    it('suppresses subsequent calls within the throttle window', () => {
      const fn = vi.fn();
      const t = new Throttler(100);
      t.throttle(fn);
      t.throttle(fn);
      t.throttle(fn);
      expect(fn).toHaveBeenCalledTimes(1);
    });

    it('allows another call after the throttle interval expires', () => {
      const fn = vi.fn();
      const t = new Throttler(100);
      t.throttle(fn);
      vi.advanceTimersByTime(150);
      t.throttle(fn);
      expect(fn).toHaveBeenCalledTimes(2);
    });

    it('does not fire a second call if the interval has not yet elapsed', () => {
      const fn = vi.fn();
      const t = new Throttler(200);
      t.throttle(fn);
      vi.advanceTimersByTime(100);
      t.throttle(fn);
      expect(fn).toHaveBeenCalledTimes(1);
    });
  });

  // -------------------------------------------------------------------------
  // debounce
  // -------------------------------------------------------------------------
  describe('debounce', () => {
    it('does not call fn immediately', () => {
      const fn = vi.fn();
      const t = new Throttler(100);
      t.debounce(fn);
      expect(fn).not.toHaveBeenCalled();
    });

    it('calls fn after the delay elapses', () => {
      const fn = vi.fn();
      const t = new Throttler(100);
      t.debounce(fn);
      vi.advanceTimersByTime(100);
      expect(fn).toHaveBeenCalledTimes(1);
    });

    it('resets the delay when called again before it fires', () => {
      const fn = vi.fn();
      const t = new Throttler(100);
      t.debounce(fn);
      vi.advanceTimersByTime(80);
      t.debounce(fn);
      vi.advanceTimersByTime(80);
      expect(fn).not.toHaveBeenCalled();
      vi.advanceTimersByTime(30);
      expect(fn).toHaveBeenCalledTimes(1);
    });

    it('calls fn only once after many rapid invocations', () => {
      const fn = vi.fn();
      const t = new Throttler(100);
      for (let i = 0; i < 10; i++) {
        t.debounce(fn);
      }
      vi.advanceTimersByTime(200);
      expect(fn).toHaveBeenCalledTimes(1);
    });

    it('fires a second call correctly after the first has resolved', () => {
      const fn = vi.fn();
      const t = new Throttler(100);
      t.debounce(fn);
      vi.advanceTimersByTime(150);
      t.debounce(fn);
      vi.advanceTimersByTime(150);
      expect(fn).toHaveBeenCalledTimes(2);
    });
  });

  // -------------------------------------------------------------------------
  // delayAsync
  // -------------------------------------------------------------------------
  describe('delayAsync', () => {
    it('does not invoke fn before the delay', async () => {
      const fn = vi.fn().mockResolvedValue('x');
      const t = new Throttler(100);
      void t.delayAsync(fn);
      expect(fn).not.toHaveBeenCalled();
    });

    it('resolves with the return value of fn', async () => {
      const fn = vi.fn().mockResolvedValue('result');
      const t = new Throttler(100);
      const promise = t.delayAsync(fn);
      vi.advanceTimersByTime(100);
      await expect(promise).resolves.toBe('result');
    });

    it('passes variadic arguments through to fn', async () => {
      const fn = vi.fn().mockImplementation(async (a: number, b: number) => a + b);
      const t = new Throttler(100);
      const promise = t.delayAsync(fn, 3, 4);
      vi.advanceTimersByTime(100);
      await expect(promise).resolves.toBe(7);
    });

    it('rejects when fn throws', async () => {
      const fn = vi.fn().mockRejectedValue(new Error('boom'));
      const t = new Throttler(100);
      const promise = t.delayAsync(fn);
      vi.advanceTimersByTime(100);
      await expect(promise).rejects.toThrow('boom');
    });

    it('cancels the previous pending call when invoked again', async () => {
      const fn = vi.fn().mockResolvedValue(42);
      const t = new Throttler(100);
      void t.delayAsync(fn);
      vi.advanceTimersByTime(50);
      const second = t.delayAsync(fn);
      vi.advanceTimersByTime(100);
      await expect(second).resolves.toBe(42);
      expect(fn).toHaveBeenCalledTimes(1);
    });
  });
});
