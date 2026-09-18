/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

let currentUser: any = { username: 'author', is_admin: false };

vi.mock('@mui/icons-material', () => ({
  Celebration: () => <div>confetti</div>,
  Check: () => <div>check</div>,
  Clear: () => <div>clear</div>,
  Delete: () => <div>delete</div>,
  Edit: () => <div>edit</div>,
  Favorite: () => <div>heart</div>,
  FireTruck: () => <div>fire</div>,
  FormatQuote: () => <div>quote</div>,
  Mood: () => <div>laugh</div>,
  MoreHoriz: () => <div>menu</div>,
  RocketLaunch: () => <div>rocket</div>,
  ThumbDown: () => <div>minus</div>,
  ThumbUp: () => <div>plus</div>
}));

vi.mock('@mui/material', () => ({
  CardActions: ({ children }: any) => <div>{children}</div>,
  CardContent: ({ children }: any) => <div>{children}</div>,
  Chip: ({ label, onClick }: any) => <button onClick={onClick}>{String(label ?? '')}</button>,
  CircularProgress: () => <div>loading</div>,
  Collapse: ({ children, in: open }: any) => open ? <div>{children}</div> : null,
  Fade: ({ children }: any) => <>{children}</>,
  IconButton: ({ children, onClick, disabled, id }: any) => <button id={id} onClick={onClick} disabled={disabled}>{children}</button>,
  ListItemIcon: ({ children }: any) => <div>{children}</div>,
  ListItemText: ({ children }: any) => <div>{children}</div>,
  Menu: ({ children, open }: any) => open ? <div>{children}</div> : null,
  MenuItem: ({ children, onClick, disabled }: any) => <button onClick={onClick} disabled={disabled}>{children}</button>,
  Stack: ({ children, onMouseEnter, onMouseLeave }: any) => <div onMouseEnter={onMouseEnter} onMouseLeave={onMouseLeave}>{children}</div>,
  TextField: ({ defaultValue, onChange, onKeyDown }: any) => (
    <textarea aria-label="comment-editor" defaultValue={defaultValue} onChange={onChange} onKeyDown={onKeyDown} />
  ),
  Tooltip: ({ children }: any) => <>{children}</>,
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('@tui/core', () => ({
  useAppUser: () => ({ user: currentUser })
}));

vi.mock('components/elements/addons/layout/FlexOne', () => ({
  default: () => <div>flex-one</div>
}));

vi.mock('components/hooks/useMyUtils', () => ({
  default: () => ({ shiftColor: () => '#999' })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('utils/utils', () => ({
  compareTimestamp: () => 2,
  twitterShort: () => 'short-time'
}));

vi.mock('./display/HowlerAvatar', () => ({
  default: ({ userId }: any) => <div>{`avatar-${userId}`}</div>
}));

vi.mock('./display/HowlerCard', () => ({
  default: ({ children, onClick, onMouseEnter, onMouseLeave }: any) => (
    <div onClick={onClick} onMouseEnter={onMouseEnter} onMouseLeave={onMouseLeave}>
      {children}
    </div>
  )
}));

vi.mock('./display/Markdown', () => ({
  default: ({ md }: any) => <div>{md}</div>
}));

import Comment from './Comment';

describe('Comment', () => {
  beforeEach(() => {
    currentUser = { username: 'author', is_admin: false };
  });

  it('quotes and deletes a comment from the action menu', async () => {
    const handleDelete = vi.fn().mockResolvedValue(undefined);
    const handleQuote = vi.fn();

    render(
      <Comment
        comment={{ id: 'c1', user: 'author', value: 'hello', timestamp: '2026-01-01T00:00:00Z', modified: '2026-01-02T00:00:00Z' } as any}
        handleDelete={handleDelete}
        handleQuote={handleQuote}
        users={{ author: { name: 'Author Name' } as any }}
        extra={<div>extra</div>}
      />
    );

    expect(screen.getByText('Author Name')).toBeInTheDocument();
    expect(screen.getByText('comments.edited')).toBeInTheDocument();
    expect(screen.getByText('hello')).toBeInTheDocument();

    fireEvent.mouseEnter(screen.getByText('hello').closest('div')!);
    fireEvent.click(screen.getByText('menu'));
    fireEvent.click(screen.getByText('comments.quote'));
    expect(handleQuote).toHaveBeenCalled();

    fireEvent.click(screen.getByText('menu'));
    fireEvent.click(screen.getByText('comments.delete'));
    await waitFor(() => expect(handleDelete).toHaveBeenCalled());
  });

  it('edits and reacts to a comment', async () => {
    const handleEdit = vi.fn().mockResolvedValue(undefined);
    const handleReact = vi.fn().mockResolvedValue(undefined);

    render(
      <Comment
        comment={{
          id: 'c2',
          user: 'author',
          value: 'old text',
          timestamp: '2026-01-01T00:00:00Z',
          modified: '2026-01-01T00:00:00Z',
          reactions: { other: 'heart' }
        } as any}
        handleEdit={handleEdit}
        handleReact={handleReact}
        users={{ author: { name: 'Author Name' } as any }}
      />
    );

    fireEvent.mouseEnter(screen.getByText('old text').closest('div')!);
    fireEvent.click(screen.getByText('menu'));
    fireEvent.click(screen.getByText('comments.edit'));

    fireEvent.change(screen.getByLabelText('comment-editor'), { target: { value: 'new text' } });
    fireEvent.keyDown(screen.getByLabelText('comment-editor'), { key: 'Enter', ctrlKey: true });

    await waitFor(() => expect(handleEdit).toHaveBeenCalledWith('new text'));

    fireEvent.click(screen.getByText('1'));
    await waitFor(() => expect(handleReact).toHaveBeenCalledWith('heart'));
  });
});
