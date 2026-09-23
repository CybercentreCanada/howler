/// <reference types="vitest" />
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockEmit = vi.hoisted(() => vi.fn());
const mockAddListener = vi.hoisted(() => vi.fn());
const mockRemoveListener = vi.hoisted(() => vi.fn());
const mockNavigate = vi.hoisted(() => vi.fn());
const mockGetMatchingAnalytic = vi.hoisted(() => vi.fn());

let socketHandler: ((data: any) => void) | undefined;

vi.mock('api', () => ({
  default: {
    hit: {
      comments: {
        post: (id: string, value: string) => ({ op: 'post', id, value }),
        del: (id: string, ids: string[]) => ({ op: 'del', id, ids }),
        put: (id: string, commentId: string, value: string) => ({ op: 'put', id, commentId, value }),
        react: {
          put: (id: string, commentId: string, type: string) => ({ op: 'react-put', id, commentId, type }),
          del: (id: string, commentId: string) => ({ op: 'react-del', id, commentId })
        }
      }
    }
  }
}));

vi.mock('@mui/icons-material', () => ({
  Clear: () => <div>clear-icon</div>,
  KeyboardArrowDown: () => <div>expand-icon</div>,
  Send: () => <div>send-icon</div>
}));

vi.mock('@mui/material', () => ({
  Accordion: ({ children }: any) => <div>{children}</div>,
  AccordionDetails: ({ children }: any) => <div>{children}</div>,
  AccordionSummary: ({ children }: any) => <div>{children}</div>,
  AvatarGroup: ({ children }: any) => <div>{children}</div>,
  Chip: ({ label, onClick }: any) => <button onClick={onClick}>{label}</button>,
  IconButton: ({ children, onClick, disabled }: any) => <button onClick={onClick} disabled={disabled}>{children}</button>,
  Skeleton: () => <div>loading</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  TextField: ({ placeholder, inputRef, onKeyDown, onChangeCapture, onFocus, onBlur, error }: any) => (
    <textarea
      aria-label={placeholder}
      ref={inputRef}
      onKeyDown={onKeyDown}
      onInput={onChangeCapture}
      onFocus={onFocus}
      onBlur={onBlur}
      data-error={error}
    />
  ),
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('@tui/core', () => ({
  useAppUser: () => ({ user: { username: 'alice' } })
}));

vi.mock('components/app/hooks/useMatchers', () => ({
  default: () => ({ getMatchingAnalytic: mockGetMatchingAnalytic })
}));

vi.mock('components/app/providers/SocketProvider', () => ({
  SocketContext: { name: 'socket-context' }
}));

vi.mock('components/elements/addons/layout/FlexOne', () => ({
  default: () => <div>flex</div>
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context?.name === 'socket-context') {
        return {
          addListener: (...args: any[]) => {
            socketHandler = args[1];
            return mockAddListener(...args);
          },
          removeListener: mockRemoveListener,
          emit: mockEmit
        };
      }

      return actual.useContext(context);
    }
  };
});

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string, params?: any) => (params?.count ? `${key}:${params.count}` : key) })
}));

vi.mock('react-router', () => ({
  useNavigate: () => mockNavigate
}));

vi.mock('utils/typeUtils', () => ({
  isHit: (record: any) => record?.__index === 'hit'
}));

vi.mock('utils/utils', () => ({
  compareTimestamp: (a: string, b: string) => new Date(a).getTime() - new Date(b).getTime(),
  sortByTimestamp: (items: any[]) => [...items].sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
}));

vi.mock('../Comment', () => ({
  default: ({ comment, extra, handleDelete, handleEdit, handleQuote, handleReact }: any) => (
    <div>
      <div>{comment.value}</div>
      {extra}
      {handleDelete && <button onClick={handleDelete}>delete-{comment.id}</button>}
      {handleEdit && <button onClick={() => handleEdit(`edited-${comment.id}`)}>edit-{comment.id}</button>}
      {handleQuote && <button onClick={handleQuote}>quote-{comment.id}</button>}
      {handleReact && <button onClick={() => handleReact('smile')}>react-{comment.id}</button>}
      {handleReact && <button onClick={() => handleReact(null)}>unreact-{comment.id}</button>}
    </div>
  )
}));

vi.mock('../display/HowlerAvatar', () => ({
  default: ({ userId }: any) => <div>{`avatar:${userId}`}</div>
}));

vi.mock('../display/TypingIndicator', () => ({
  default: () => <div>typing-indicator</div>
}));

import RecordComments from './RecordComments';

describe('RecordComments', () => {
  beforeEach(() => {
    socketHandler = undefined;
    mockDispatchApi.mockReset();
    mockEmit.mockReset();
    mockAddListener.mockReset();
    mockRemoveListener.mockReset();
    mockNavigate.mockReset();
    mockGetMatchingAnalytic.mockReset();
  });

  it('submits comments, reacts to socket typing, and routes analytic comment chips', async () => {
    mockGetMatchingAnalytic.mockResolvedValue({
      analytic_id: 'analytic-1',
      comment: [{ id: 'analytic-comment', value: 'analytic note', timestamp: '2026-01-01T00:00:00Z', detection: 'det-1' }]
    });
    mockDispatchApi.mockResolvedValue({
      howler: {
        comment: [{ id: 'comment-2', value: 'saved comment', timestamp: '2026-01-02T00:00:00Z', reactions: {} }]
      }
    });

    render(
      <RecordComments
        users={{ alice: { name: 'Alice' } as any, bob: { name: 'Bob' } as any }}
        record={{
          __index: 'hit',
          howler: {
            id: 'hit-1',
            analytic: 'Rule 1',
            detection: 'det-1',
            comment: [{ id: 'comment-1', value: 'existing comment', timestamp: '2026-01-01T00:00:00Z', reactions: {} }]
          }
        } as any}
      />
    );

    const input = screen.getByLabelText('comments.add');
    fireEvent.focus(input);
    expect(mockEmit).toHaveBeenCalledWith({ broadcast: true, action: 'typing', id: 'hit-1' });

    fireEvent.change(input, { target: { value: 'new comment' } });
    fireEvent.keyDown(input, { key: 'Enter', ctrlKey: true, currentTarget: input });

    await waitFor(() =>
      expect(mockDispatchApi).toHaveBeenCalledWith({ op: 'post', id: 'hit-1', value: 'new comment' }, expect.any(Object))
    );
    expect(screen.getByText('saved comment')).toBeInTheDocument();

    await act(async () => {
      socketHandler?.({ event: { action: 'typing', username: 'bob' } });
    });
    expect(screen.getByText('typing-indicator')).toBeInTheDocument();
    expect(screen.getByText('avatar:bob')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Rule 1 - det-1'));
    expect(mockNavigate).toHaveBeenCalledWith('/analytics/analytic-1?tab=comments&filter=det-1');

    fireEvent.blur(input);
    expect(mockEmit).toHaveBeenCalledWith({ broadcast: true, action: 'stop_typing', id: 'hit-1' });
  });
});
