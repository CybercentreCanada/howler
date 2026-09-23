/// <reference types="vitest" />
import { act, render, renderHook, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockNavigate = vi.hoisted(() => vi.fn());
const mockSearchPost = vi.hoisted(() => vi.fn());

vi.mock('@mui/material', () => ({
  Alert: ({ children }: any) => <div>{children}</div>,
  Box: ({ children }: any) => <div>{children}</div>,
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('api', () => ({
  default: {
    search: {
      hit: {
        post: mockSearchPost
      }
    }
  }
}));

vi.mock('components/elements/hit/HitPreview', () => ({
  default: ({ hit }: any) => <div>{hit.howler.id}</div>
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-router', () => ({
  Link: ({ children, to }: any) => <a href={to}>{children}</a>,
  useNavigate: () => mockNavigate
}));

vi.mock('./useMyLocalStorage', () => ({
  useMyLocalStorageItem: () => [25]
}));

import useMySearch from './useMySearch';

describe('useMySearch', () => {
  beforeEach(() => {
    mockNavigate.mockReset();
    mockSearchPost.mockReset();
  });

  it('searches hits and maps results into quick-search items', async () => {
    mockSearchPost.mockResolvedValue({
      items: [{ howler: { id: 'hit-1' } }, { howler: { id: 'hit-2' } }]
    });
    const set = vi.fn();
    const state = { items: [], set, searching: false } as any;
    const { result } = renderHook(() => useMySearch());

    await result.current.onEnter('alpha/beta', state);

    expect(mockSearchPost).toHaveBeenCalledWith({
      offset: 0,
      rows: 25,
      query:
        'howler.assignment:*alpha\\/beta* OR howler.analytic:*alpha\\/beta* OR howler.detection:*alpha\\/beta* OR howler.status:*alpha\\/beta*'
    });
    expect(set).toHaveBeenLastCalledWith({
      ...state,
      searching: false,
      items: [
        { id: 'hit-1', item: { howler: { id: 'hit-1' } } },
        { id: 'hit-2', item: { howler: { id: 'hit-2' } } }
      ]
    });
  });

  it('handles missing state, empty responses, and thrown errors', async () => {
    const { result } = renderHook(() => useMySearch());
    await expect(result.current.onEnter('ignored')).resolves.toBeUndefined();

    const set = vi.fn();
    const state = { items: [{ id: 'x' }], set, searching: false } as any;

    mockSearchPost.mockResolvedValueOnce(null);
    await act(async () => {
      await result.current.onEnter('bad', state);
    });
    expect(set).toHaveBeenLastCalledWith({ ...state, searching: false, items: [] });

    mockSearchPost.mockRejectedValueOnce(new Error('boom'));
    await act(async () => {
      await result.current.onEnter('bad', state);
    });
    expect(set).toHaveBeenLastCalledWith({ ...state, searching: false, items: [] });
  });

  it('renders quick-search header states, item links, and navigates on selection', async () => {
    const { result, rerender } = renderHook(() => useMySearch());

    render(result.current.headerRenderer({ items: undefined, searching: false, set: vi.fn() } as any) as any);
    expect(screen.getByText('hit.quicksearch')).toBeInTheDocument();

    const set = vi.fn();
    mockSearchPost.mockResolvedValueOnce(null);
    await act(async () => {
      await result.current.onEnter('broken', { items: [], searching: false, set } as any);
    });
    rerender();
    render(result.current.headerRenderer({ items: [], searching: false, set } as any) as any);
    expect(screen.getByText('hit.search.invalid')).toBeInTheDocument();

    render(result.current.itemRenderer({ id: 'hit-9', item: { howler: { id: 'hit-9' } } } as any) as any);
    expect(screen.getByRole('link')).toHaveAttribute('href', '/hits/hit-9');
    expect(screen.getByText('hit-9')).toBeInTheDocument();

    result.current.onItemSelect({ item: { howler: { id: 'hit-9' } } } as any);
    expect(mockNavigate).toHaveBeenCalledWith('/hits/hit-9');
  });
});
