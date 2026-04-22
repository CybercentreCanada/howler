import { render, screen } from '@testing-library/react';
import { SocketContext } from 'components/app/providers/SocketProvider';
import type { ReactNode } from 'react';
import { createMockHit } from 'tests/utils';
import { describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Hoisted mocks
// ---------------------------------------------------------------------------

vi.mock('commons/components/app/hooks', () => ({
  useAppUser: () => ({ user: { username: 'current-user' } })
}));

vi.mock('components/elements/display/HowlerAvatar', () => ({
  default: ({ userId }: { userId: string }) => <div id={`avatar-${userId}`}>{userId}</div>
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key
  })
}));

// ---------------------------------------------------------------------------
// Import after mocks
// ---------------------------------------------------------------------------

import { HitLayout } from '../HitLayout';
import Assigned from './Assigned';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const createWrapper = (viewers: Record<string, string[]>) => {
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <SocketContext.Provider
      value={
        {
          viewers,
          addListener: vi.fn(),
          removeListener: vi.fn(),
          emit: vi.fn(),
          status: 1,
          reconnect: vi.fn(),
          isOpen: () => true,
          fetchViewers: vi.fn()
        } as any
      }
    >
      {children}
    </SocketContext.Provider>
  );
  return Wrapper;
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Assigned', () => {
  it('renders the assignment avatar', () => {
    const hit = createMockHit({ howler: { assignment: 'analyst-1' } });

    render(<Assigned hit={hit} layout={HitLayout.COMFY} />, { wrapper: createWrapper({}) });

    expect(screen.getByTestId('avatar-analyst-1')).toBeInTheDocument();
  });

  it('renders viewer avatars from socket context, filtering out current user', () => {
    const hit = createMockHit({ howler: { id: 'hit-1', assignment: 'analyst-1' } });

    render(<Assigned hit={hit} layout={HitLayout.COMFY} />, {
      wrapper: createWrapper({ 'hit-1': ['viewer-a', 'viewer-b', 'current-user'] })
    });

    expect(screen.getByTestId('avatar-viewer-a')).toBeInTheDocument();
    expect(screen.getByTestId('avatar-viewer-b')).toBeInTheDocument();
    expect(screen.queryByText('current-user')).not.toBeInTheDocument();
  });

  it('renders no viewer avatars when no viewers exist', () => {
    const hit = createMockHit({ howler: { id: 'hit-2', assignment: 'analyst-1' } });

    render(<Assigned hit={hit} layout={HitLayout.COMFY} />, { wrapper: createWrapper({}) });

    expect(screen.getByTestId('avatar-analyst-1')).toBeInTheDocument();
    expect(screen.queryByTestId('avatar-viewer-a')).not.toBeInTheDocument();
  });
});
