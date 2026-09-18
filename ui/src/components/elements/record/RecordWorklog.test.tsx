/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

let versions: Record<string, string> = {};
const mockSetVersions = vi.hoisted(() => vi.fn((next: Record<string, string>) => { versions = next; }));

vi.mock('components/hooks/useMyLocalStorage', () => ({
  useMyLocalStorageItem: () => [versions, mockSetVersions]
}));

vi.mock('components/hooks/useMyUtils', () => ({
  default: () => ({ shiftColor: (color: string) => color })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('utils/constants', () => ({
  StorageKey: { LAST_SEEN: 'LAST_SEEN' }
}));

vi.mock('utils/utils', () => ({
  compareTimestamp: (a: string, b: string) => new Date(a).getTime() - new Date(b).getTime(),
  twitterShort: (value: string) => `short:${value}`
}));

vi.mock('../display/HowlerAvatar', () => ({
  default: ({ userId }: any) => <div>{`avatar:${userId}`}</div>
}));

vi.mock('../display/HowlerCard', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

vi.mock('../display/Markdown', () => ({
  default: ({ md }: any) => <div>{`markdown:${md}`}</div>
}));

import RecordWorklog from './RecordWorklog';

describe('RecordWorklog', () => {
  beforeEach(() => {
    versions = {};
    mockSetVersions.mockClear();
  });

  it('renders grouped worklog entries and marks new entries', () => {
    const { unmount } = render(
      <RecordWorklog
        users={{ alice: { name: 'Alice' } as any }}
        record={{
          __index: 'hit',
          howler: {
            id: 'hit-1',
            log: [
              { user: 'alice', previous_version: 'v3', timestamp: '2026-01-03T00:00:00Z', explanation: ' hello ' },
              { user: 'alice', previous_version: 'v2', timestamp: '2026-01-02T00:03:00Z', key: 'status', type: 'set', previous_value: 'open', new_value: 'closed' },
              { user: 'bob', previous_version: 'v1', timestamp: '2026-01-02T00:00:00Z', key: 'labels', type: 'appended', previous_value: '[old]', new_value: 'new' }
            ]
          }
        } as any}
      />
    );

    expect(screen.getAllByText('avatar:alice').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Alice').length).toBeGreaterThan(0);
    expect(screen.getByText('markdown:hello')).toBeInTheDocument();
    expect(screen.getByText('short:2026-01-03T00:00:00Z')).toBeInTheDocument();
    expect(screen.getByText(/hit\.worklog\.set/)).toBeInTheDocument();
    expect(screen.getByText(/hit\.worklog\.appended/)).toBeInTheDocument();

    unmount();
    expect(mockSetVersions).toHaveBeenCalled();
  });

});
