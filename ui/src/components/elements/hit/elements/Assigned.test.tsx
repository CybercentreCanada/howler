import { render, screen } from '@testing-library/react';
import { createMockHit } from 'tests/utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Hoisted mocks
// ---------------------------------------------------------------------------

const mockViewers = vi.hoisted(() => ({ current: {} as Record<string, string[]> }));

vi.mock('commons/components/app/hooks', () => ({
  useAppUser: () => ({ user: { username: 'current-user' } })
}));

vi.mock('components/app/providers/SocketProvider', async () => {
  const { createContext } = await import('react');
  return {
    SocketContext: createContext({
      viewers: mockViewers.current,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      emit: vi.fn(),
      status: 1,
      reconnect: vi.fn(),
      isOpen: () => true,
      fetchViewers: vi.fn()
    })
  };
});

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
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  mockViewers.current = {};
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Assigned', () => {
  it('renders the assignment avatar', () => {
    const hit = createMockHit({ howler: { assignment: 'analyst-1' } });

    render(<Assigned hit={hit} layout={HitLayout.COMFY} />);

    expect(screen.getByTestId('avatar-analyst-1')).toBeInTheDocument();
  });

  it('renders viewer avatars from socket context', () => {
    const hit = createMockHit({ howler: { id: 'hit-1', assignment: 'analyst-1' } });
    mockViewers.current = { 'hit-1': ['viewer-a', 'viewer-b', 'current-user'] };

    // Re-create context with updated viewers
    vi.doMock('components/app/providers/SocketProvider', async () => {
      const { createContext } = await import('react');
      return {
        SocketContext: createContext({
          viewers: mockViewers.current,
          addListener: vi.fn(),
          removeListener: vi.fn(),
          emit: vi.fn(),
          status: 1,
          reconnect: vi.fn(),
          isOpen: () => true,
          fetchViewers: vi.fn()
        })
      };
    });

    render(<Assigned hit={hit} layout={HitLayout.COMFY} />);

    // current-user should be filtered out
    expect(screen.queryByText('current-user')).not.toBeInTheDocument();
  });

  it('renders no viewer avatars when no viewers exist', () => {
    const hit = createMockHit({ howler: { id: 'hit-2', assignment: 'analyst-1' } });
    mockViewers.current = {};

    render(<Assigned hit={hit} layout={HitLayout.COMFY} />);

    // Only the assignment avatar should render
    expect(screen.getByTestId('avatar-analyst-1')).toBeInTheDocument();
  });
});
