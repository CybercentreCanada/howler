/// <reference types="vitest" />
import { act, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const socketContextToken = vi.hoisted(() => ({ name: 'socket-context' }));
const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockAddListener = vi.hoisted(() => vi.fn());
const mockRemoveListener = vi.hoisted(() => vi.fn());

vi.mock('api', () => ({
  default: {
    v2: {
      search: {
        post: (_indexes: string[], body: any) => body
      }
    }
  }
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('./SocketProvider', () => ({
  SocketContext: socketContextToken
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === socketContextToken) {
        return { addListener: mockAddListener, removeListener: mockRemoveListener };
      }
      return actual.useContext(context);
    }
  };
});

import RecordProvider, { useRecordContextSelector } from './RecordProvider';

const Consumer = () => {
  const records = useRecordContextSelector(ctx => ctx.records);
  const selected = useRecordContextSelector(ctx => ctx.selectedRecords);
  const loadRecords = useRecordContextSelector(ctx => ctx.loadRecords);
  const updateRecord = useRecordContextSelector(ctx => ctx.updateRecord);
  const getRecord = useRecordContextSelector(ctx => ctx.getRecord);
  const addRecordToSelection = useRecordContextSelector(ctx => ctx.addRecordToSelection);
  const removeRecordFromSelection = useRecordContextSelector(ctx => ctx.removeRecordFromSelection);
  const clearSelectedRecords = useRecordContextSelector(ctx => ctx.clearSelectedRecords);

  return (
    <div>
      <button onClick={() => loadRecords([{ howler: { id: 'h1' } }, { howler: { id: 'h2' } }] as any)}>load</button>
      <button onClick={() => updateRecord({ howler: { id: 'h2' }, updated: true } as any)}>update</button>
      <button onClick={() => addRecordToSelection('h1')}>select-one</button>
      <button onClick={() => addRecordToSelection('missing')}>select-missing</button>
      <button onClick={() => removeRecordFromSelection('h1')}>remove</button>
      <button onClick={() => clearSelectedRecords('h2')}>clear-except</button>
      <button onClick={() => void getRecord('missing').then(r => (document.body.dataset.record = r.howler.id))}>fetch</button>
      <span>{Object.keys(records).join(',')}</span>
      <span>{selected.map((item: any) => item.howler.id).join(',')}</span>
    </div>
  );
};

describe('RecordProvider', () => {
  it('loads, updates, selects, and fetches records while wiring socket listeners', async () => {
    mockDispatchApi.mockResolvedValue({ items: [{ howler: { id: 'missing' } }] });
    render(
      <RecordProvider>
        <Consumer />
      </RecordProvider>
    );

    expect(mockAddListener).toHaveBeenCalledWith('hits', expect.any(Function));
    await act(async () => screen.getByText('load').click());
    expect(screen.getByText('h1,h2')).toBeInTheDocument();

    await act(async () => screen.getByText('update').click());
    await act(async () => screen.getByText('select-one').click());
    expect(screen.getByText('h1')).toBeInTheDocument();

    await act(async () => screen.getByText('select-missing').click());
    await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
    await act(async () => screen.getByText('fetch').click());
    expect(document.body.dataset.record).toBe('missing');

    await act(async () => screen.getByText('clear-except').click());
    expect(screen.getByText('h2')).toBeInTheDocument();
    await act(async () => screen.getByText('remove').click());
  });
});
