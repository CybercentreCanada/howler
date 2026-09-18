/// <reference types="vitest" />
import { act, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockGetAvatar = vi.hoisted(() => vi.fn());
const avatarContextToken = vi.hoisted(() => ({ name: 'avatar-context' }));

vi.mock('@mui/material', () => ({
  Avatar: ({ children, src, ...rest }: any) => <div data-src={src} {...rest}>{children}</div>,
  Tooltip: ({ children }: any) => <div>{children}</div>,
  useTheme: () => ({ palette: { getContrastText: () => '#fff' } })
}));

vi.mock('components/app/providers/AvatarProvider', () => ({
  AvatarContext: avatarContextToken
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === avatarContextToken) return { getAvatar: mockGetAvatar };
      return actual.useContext(context);
    }
  };
});

import HowlerAvatar from './HowlerAvatar';

describe('HowlerAvatar', () => {
  beforeEach(() => {
    mockGetAvatar.mockReset();
  });

  it('renders unknown and unassigned fallback labels', () => {
    render(
      <div>
        <HowlerAvatar userId="" />
        <HowlerAvatar userId="unassigned" />
      </div>
    );

    expect(screen.getByLabelText('unknown')).toBeInTheDocument();
    expect(screen.getByLabelText('app.drawer.hit.assignment.unassigned.name')).toBeInTheDocument();
  });

  it('uses remote image sources directly and derives initials for non-url avatars', async () => {
    mockGetAvatar.mockResolvedValueOnce('https://example.com/avatar.png').mockResolvedValueOnce('Alice Example');

    const { rerender } = render(
      <HowlerAvatar userId="alice" />
    );

    await waitFor(() => expect(screen.getByLabelText('alice')).toHaveAttribute('data-src', 'https://example.com/avatar.png'));

    rerender(
      <HowlerAvatar userId="bob" />
    );

    await waitFor(() => expect(screen.getByLabelText('bob')).toHaveTextContent('AE'));
  });

  it('handles avatar lookup failures by clearing the src', async () => {
    const debugSpy = vi.spyOn(console, 'debug').mockImplementation(() => undefined);
    mockGetAvatar.mockRejectedValueOnce(new Error('no avatar'));

    render(
      <HowlerAvatar userId="charlie" />
    );

    await act(async () => {});
    expect(debugSpy).toHaveBeenCalled();
    expect(screen.getByLabelText('charlie')).not.toHaveAttribute('data-src', 'https://example.com/avatar.png');
  });
});
