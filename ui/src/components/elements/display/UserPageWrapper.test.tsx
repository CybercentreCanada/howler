/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('@mui/material', () => ({
  Grid: ({ children }: any) => <div>{children}</div>,
  Stack: ({ children }: any) => <div>{children}</div>
}));

vi.mock('@tui/core', () => ({
  PageCenter: ({ children }: any) => <div>{children}</div>
}));

vi.mock('./HowlerAvatarHeader', () => ({
  default: ({ user }: any) => <div>{`avatar:${user.username}`}</div>
}));

import UserPageWrapper from './UserPageWrapper';

describe('UserPageWrapper', () => {
  it('renders the avatar header and nested content', () => {
    render(
      <UserPageWrapper user={{ username: 'alice' } as any}>
        <div>child-content</div>
      </UserPageWrapper>
    );

    expect(screen.getByText('avatar:alice')).toBeInTheDocument();
    expect(screen.getByText('child-content')).toBeInTheDocument();
  });
});
