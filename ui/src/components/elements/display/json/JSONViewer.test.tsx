import { act, render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import JSONViewer from './JSONViewer';

vi.mock('commons/components/app/hooks', () => ({
  useAppTheme: () => ({ isDark: false })
}));

vi.mock('components/elements/addons/search/phrase/Phrase', () => ({
  default: () => <input />
}));

vi.mock('components/hooks/useMyLocalStorage', () => ({
  useMyLocalStorageItem: <T,>(_key: string, defaultValue?: T) => [defaultValue]
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('utils/utils', () => ({
  removeEmpty: vi.fn(),
  searchObject: vi.fn()
}));

describe('JSONViewer', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('does not process a debounced result after unmounting', async () => {
    vi.useFakeTimers();
    const { removeEmpty } = await import('utils/utils');
    const { unmount } = render(<JSONViewer data={{ value: 'visible' }} />);

    unmount();
    act(() => {
      vi.advanceTimersByTime(150);
    });

    expect(removeEmpty).not.toHaveBeenCalled();
  });
});
