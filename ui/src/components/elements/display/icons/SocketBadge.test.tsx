/// <reference types="vitest" />
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const reconnect = vi.fn();
const socketContextToken = vi.hoisted(() => ({ name: 'socket-context' }));
let socketValue: any = { status: 0, reconnect };

vi.mock('@mui/icons-material', () => ({
  CloudSync: () => <div>cloud-sync</div>
}));

vi.mock('@mui/material', () => ({
  Badge: ({ children }: any) => <div>{children}</div>,
  IconButton: ({ children, onClick }: any) => <button onClick={onClick}>{children}</button>,
  Tooltip: ({ children, title }: any) => <div data-title={title}>{children}</div>,
  styled: (component: any) => () => component
}));

vi.mock('i18n', () => ({
  default: {
    t: (key: string) => `translated:${key}`
  }
}));

vi.mock('components/app/providers/SocketProvider', () => ({
  SocketContext: socketContextToken,
  Status: { CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3 }
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === socketContextToken) return socketValue;
      return actual.useContext(context);
    }
  };
});

import SocketBadge from './SocketBadge';

describe('SocketBadge', () => {
  it('renders translated titles and reconnects on click', () => {
    socketValue = { status: 0, reconnect };
    const { rerender, container } = render(<SocketBadge />);

    expect(container.querySelector('[data-title="translated:live.connecting"]')).toBeTruthy();

    socketValue = { status: 3, reconnect };
    rerender(<SocketBadge size="large" />);

    expect(container.querySelector('[data-title="translated:live.closed"]')).toBeTruthy();
    fireEvent.click(screen.getByRole('button'));
    expect(reconnect).toHaveBeenCalled();
  });
});
