import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { Item } from 'models/entities/generated/Item';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('react-router', async () => {
  const actual = await vi.importActual('react-router');
  return {
    ...actual,
    Link: ({ to, children, ...props }: any) => (
      <a href={to} {...props}>
        {children}
      </a>
    ),
    useLocation: vi.fn(() => ({ pathname: '/', search: '' }))
  };
});

const mockDraggable = vi.hoisted(() => ({
  isDragging: false,
  transform: null as any
}));

vi.mock('@dnd-kit/core', () => ({
  useDraggable: vi.fn(() => ({
    attributes: {},
    listeners: {},
    setNodeRef: vi.fn(),
    transform: mockDraggable.transform,
    isDragging: mockDraggable.isDragging,
    active: null
  })),
  useDroppable: vi.fn(() => ({
    setNodeRef: vi.fn(),
    isOver: false
  }))
}));

vi.mock('@dnd-kit/utilities', () => ({
  CSS: { Transform: { toString: (t: any) => (t ? `translate3d(${t.x}px,${t.y}px,0)` : '') } }
}));

import { useDraggable, useDroppable } from '@dnd-kit/core';
import FolderEntry from './FolderEntry';

const hitItem = (value: string, id = value): Item => ({ type: 'hit', value, id, name: value });

const renderEntry = (props: Partial<React.ComponentPropsWithoutRef<typeof FolderEntry>> = {}) => {
  const entry = props.entry ?? hitItem('my-hit', 'item-1');
  return render(
    <MemoryRouter>
      <FolderEntry caseId="case-1" indent={1} label="my label" entry={entry} {...props} />
    </MemoryRouter>
  );
};

beforeEach(() => {
  mockDraggable.isDragging = false;
  mockDraggable.transform = null;
  vi.mocked(useDroppable).mockReturnValue({ setNodeRef: vi.fn(), isOver: false } as any);
});

describe('FolderEntry', () => {
  it('opens reference links in a new tab', () => {
    renderEntry({
      entry: { id: 'ref-1', type: 'reference', value: 'https://example.com', name: 'ext' },
      to: 'https://example.com',
      label: 'ext'
    });
    const el = screen.getByText('ext').closest('a');
    expect(el).toHaveAttribute('target', '_blank');
    expect(el).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('shows chevron for folder entries', () => {
    const { container } = renderEntry({ entry: { id: 'f1', type: 'folder', value: 'Folder', name: 'Folder' } });
    const chevron = container.querySelector('svg');
    expect(chevron).toBeInTheDocument();
  });

  it('enables folder droppable when not dragging and caseId is set', () => {
    renderEntry({ caseId: 'case-1', entry: { id: 'f1', type: 'folder', value: 'Folder', name: 'Folder' } });
    expect(vi.mocked(useDroppable)).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'case-1:folder:f1', disabled: false })
    );
  });

  it('passes namespaced id to useDroppable', () => {
    renderEntry({ caseId: 'case-1', entry: { id: 'folder-id', type: 'folder', value: 'Folder', name: 'Folder' } });
    expect(vi.mocked(useDroppable)).toHaveBeenCalledWith(expect.objectContaining({ id: 'case-1:folder:folder-id' }));
  });

  it('falls back to undefined id segment when entry has no id', async () => {
    renderEntry({ caseId: null, label: 'my label', entry: { type: 'hit', value: 'v1', name: 'my label' } });
    expect(vi.mocked(useDraggable)).toHaveBeenCalledWith(expect.objectContaining({ id: ':hit:undefined' }));
  });

  it('calls onClick when clicked', async () => {
    const onClick = vi.fn();
    renderEntry({ onClick });
    await userEvent.click(screen.getByText('my label'));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
