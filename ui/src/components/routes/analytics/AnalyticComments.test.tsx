/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());

let appUserValue: any = { user: { username: 'demo' } };
let searchParamsValue = new URLSearchParams();

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return {
    ...actual,
    Clear: () => <div>clear-icon</div>,
    Send: () => <div>send-icon</div>
  };
});

vi.mock('@mui/material', () => ({
  Chip: ({ label }: any) => <div>{label}</div>,
  Divider: () => <div>divider</div>,
  IconButton: ({ children, onClick, disabled }: any) => <button disabled={disabled} onClick={onClick}>{children}</button>,
  Stack: ({ children }: any) => <div>{children}</div>,
  TextField: ({ inputRef, onKeyDown, onChangeCapture, placeholder }: any) => (
    <textarea
      aria-label={placeholder}
      ref={inputRef}
      onKeyDown={onKeyDown}
      onChange={onChangeCapture}
    />
  ),
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('@tui/core', () => ({
  useAppUser: () => appUserValue
}));

vi.mock('api', () => ({
  default: {
    analytic: {
      comments: {
        post: (analyticId: string, value: string, filter?: string) => ({ analyticId, value, filter, op: 'post' }),
        del: (analyticId: string, ids: string[]) => ({ analyticId, ids, op: 'del' }),
        put: (analyticId: string, commentId: string, value: string) => ({ analyticId, commentId, value, op: 'put' }),
        react: {
          put: (analyticId: string, commentId: string, type: string) => ({ analyticId, commentId, type, op: 'react-put' }),
          del: (analyticId: string, commentId: string) => ({ analyticId, commentId, op: 'react-del' })
        }
      }
    }
  }
}));

vi.mock('components/elements/addons/layout/FlexOne', () => ({
  default: () => <div>flex</div>
}));

vi.mock('components/elements/Comment', () => ({
  default: ({ comment, handleDelete, handleEdit, handleQuote, handleReact, extra }: any) => (
    <div>
      <div>{comment.value}</div>
      <button onClick={handleDelete}>delete-{comment.id}</button>
      <button onClick={() => handleEdit(`edit-${comment.id}`)}>edit-{comment.id}</button>
      <button onClick={handleQuote}>quote-{comment.id}</button>
      <button onClick={() => handleReact('thumbs_up')}>react-{comment.id}</button>
      <button onClick={() => handleReact(null)}>unreact-{comment.id}</button>
      {extra}
    </div>
  )
}));

vi.mock('components/elements/display/HowlerAvatar', () => ({
  default: ({ userId }: any) => <div>{`avatar:${userId}`}</div>
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('components/hooks/useMyUserList', () => ({
  default: () => ({ demo: { username: 'demo' }, user2: { username: 'user2' } })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-router', () => ({
  useSearchParams: () => [searchParamsValue]
}));

import AnalyticComments from './AnalyticComments';

describe('AnalyticComments', () => {
  beforeEach(() => {
    appUserValue = { user: { username: 'demo' } };
    searchParamsValue = new URLSearchParams();
    mockDispatchApi.mockReset().mockImplementation(async value => value);
  });

  it('submits comments and clears the input', async () => {
    const setAnalytic = vi.fn();
    mockDispatchApi.mockResolvedValueOnce({ analytic_id: 'an-1', comment: [] });

    render(<AnalyticComments analytic={{ analytic_id: 'an-1', comment: [] } as any} setAnalytic={setAnalytic} />);

    const input = screen.getByLabelText('comments.add.analytic');
    fireEvent.change(input, { target: { value: 'hello world' } });
    fireEvent.keyDown(input, { key: 'Enter', ctrlKey: true });

    await Promise.resolve();
    await Promise.resolve();
    await waitFor(() =>
      expect(mockDispatchApi).toHaveBeenCalledWith(
        { analyticId: 'an-1', value: 'hello world', filter: undefined, op: 'post' },
        { showError: true, throwError: true, logError: false }
      )
    );
    expect(setAnalytic).toHaveBeenCalledWith({ analytic_id: 'an-1', comment: [] });
    expect(input).toHaveValue('');
  });

  it('supports quoting comment text into the input', async () => {
    vi.useFakeTimers();
    const setAnalytic = vi.fn();
    render(
      <AnalyticComments
        analytic={{
          analytic_id: 'an-1',
          comment: [{ id: 'c1', user: 'demo', value: 'line one\nline two', timestamp: '2024-01-01T00:00:00Z' }]
        } as any}
        setAnalytic={setAnalytic}
      />
    );

    fireEvent.click(screen.getByText('quote-c1'));
    await vi.advanceTimersByTimeAsync(20);
    expect(screen.getByLabelText('comments.add.analytic')).toHaveValue('> line one\n> line two\n\n');
    vi.useRealTimers();
  });

  it('filters comments and supports clear, delete, edit, and react flows', async () => {
    const setAnalytic = vi.fn();
    searchParamsValue = new URLSearchParams('filter=Det-1');
    const analytic = {
      analytic_id: 'an-1',
      comment: [
        { id: 'c1', user: 'demo', value: 'first', detection: 'Det-1', timestamp: '2024-01-02T00:00:00Z', reactions: { other: 'smile' } },
        { id: 'c2', user: 'user2', value: 'second', detection: 'Det-2', timestamp: '2024-01-01T00:00:00Z', reactions: { demo: 'smile' } }
      ]
    };

    render(<AnalyticComments analytic={analytic as any} setAnalytic={setAnalytic} />);

    expect(screen.getByText('first')).toBeInTheDocument();
    expect(screen.queryByText('second')).not.toBeInTheDocument();

    const input = screen.getByLabelText('comments.add.detection');
    fireEvent.change(input, { target: { value: 'abc' } });
    fireEvent.keyDown(input, { key: 'a' });
    fireEvent.click(screen.getByText('clear-icon'));
    expect(input).toHaveValue('');

    fireEvent.click(screen.getByText('delete-c1'));
    expect(mockDispatchApi).toHaveBeenCalledWith({ analyticId: 'an-1', ids: ['c1'], op: 'del' });
    await Promise.resolve();
    await Promise.resolve();
    expect(setAnalytic).toHaveBeenCalledWith({
      ...analytic,
      comment: [analytic.comment[1]]
    });

    fireEvent.click(screen.getByText('edit-c1'));
    expect(mockDispatchApi).toHaveBeenCalledWith({ analyticId: 'an-1', commentId: 'c1', value: 'edit-c1', op: 'put' });
    await Promise.resolve();
    await Promise.resolve();

    fireEvent.click(screen.getByText('react-c1'));
    expect(mockDispatchApi).toHaveBeenCalledWith({ analyticId: 'an-1', commentId: 'c1', type: 'thumbs_up', op: 'react-put' });
    await Promise.resolve();
    await Promise.resolve();

    fireEvent.click(screen.getByText('unreact-c1'));
    expect(mockDispatchApi).toHaveBeenCalledWith({ analyticId: 'an-1', commentId: 'c1', op: 'react-del' });
  });
});
