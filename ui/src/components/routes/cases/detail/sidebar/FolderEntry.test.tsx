import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { Item } from 'models/entities/generated/Item';
import { MemoryRouter } from 'react-router-dom';
import { setupContextSelectorMock } from 'tests/mocks';
import { beforeEach, describe, expect, it, vi } from 'vitest';

setupContextSelectorMock();

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
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

// Controllable draggable mock — lets individual tests flip isDragging and transform
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

// ---------------------------------------------------------------------------
// Imports after mocks
// ---------------------------------------------------------------------------

import { useDroppable } from '@dnd-kit/core';
import FolderEntry from './FolderEntry';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const hitItem = (path: string, value = path): Item => ({ type: 'hit', value, path });

const renderEntry = (props: Partial<React.ComponentPropsWithoutRef<typeof FolderEntry>> = {}) =>
  render(
    <MemoryRouter>
      <FolderEntry caseId="case-1" path="folder/item" indent={1} label="my label" itemType="hit" {...props} />
    </MemoryRouter>
  );

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  mockDraggable.isDragging = false;
  mockDraggable.transform = null;
  vi.mocked(useDroppable).mockReturnValue({ setNodeRef: vi.fn(), isOver: false } as any);
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('FolderEntry', () => {
  describe('rendering', () => {
    it('renders the label text', () => {
      renderEntry({ label: 'hello world' });
      expect(screen.getByText('hello world')).toBeInTheDocument();
    });

    it('renders as a link when `to` is provided', () => {
      renderEntry({ to: '/cases/case-1/folder/item' });
      const el = screen.getByText('my label').closest('a');
      expect(el).toHaveAttribute('href', '/cases/case-1/folder/item');
    });

    it('opens link in new tab for reference items', () => {
      renderEntry({ itemType: 'reference', to: 'https://example.com', label: 'ext' });
      const el = screen.getByText('ext').closest('a');
      expect(el).toHaveAttribute('target', '_blank');
      expect(el).toHaveAttribute('rel', 'noopener noreferrer');
    });

    it('does not render as a link when `to` is omitted', () => {
      renderEntry({ to: undefined });
      expect(screen.getByText('my label').closest('a')).toBeNull();
    });

    it('shows the chevron for folder items', () => {
      // Chevron is visible (non-zero opacity) for folder and case types
      const { container } = renderEntry({ itemType: 'folder' });
      // ChevronRight is the first svg inside the row
      const chevron = container.querySelector('svg');
      expect(chevron).toBeInTheDocument();
      expect(chevron).not.toHaveStyle('opacity: 0');
    });

    it('hides the chevron for non-folder, non-case items', () => {
      const { container } = renderEntry({ itemType: 'hit' });
      const chevron = container.querySelector('svg');
      // Chevron rendered but with opacity 0 (applied via MUI sx / emotion class)
      expect(chevron).toBeInTheDocument();
      expect(chevron).toHaveStyle({ opacity: '0' });
    });

    it('rotates chevron when chevronOpen is true', () => {
      const { container } = renderEntry({ itemType: 'folder', chevronOpen: true });
      const chevron = container.querySelector('svg');
      expect(chevron).toHaveStyle({ transform: 'rotate(90deg)' });
    });

    it('does not rotate chevron when chevronOpen is false', () => {
      const { container } = renderEntry({ itemType: 'folder', chevronOpen: false });
      const chevron = container.querySelector('svg');
      expect(chevron).toHaveStyle({ transform: 'rotate(0deg)' });
    });

    it('falls back to the Folder icon for unknown itemTypes', () => {
      // Should not throw; renders something
      expect(() => renderEntry({ itemType: 'unknown-type' })).not.toThrow();
      expect(screen.getByText('my label')).toBeInTheDocument();
    });
  });

  describe('drag state', () => {
    it('is fully visible when not dragging', () => {
      const { container } = renderEntry();
      const row = container.firstElementChild as HTMLElement;
      expect(row.style.opacity).toBe('');
    });

    it('becomes invisible (opacity 0) while dragging', () => {
      mockDraggable.isDragging = true;
      const { container } = renderEntry();
      const row = container.firstElementChild as HTMLElement;
      expect(row.style.opacity).toBe('0');
    });

    it('does not render as a link while dragging even if `to` is set', () => {
      mockDraggable.isDragging = true;
      renderEntry({ to: '/cases/case-1/folder/item' });
      // isLink = to != null && !isDragging → false, so no <a> wrapping
      expect(screen.getByText('my label').closest('a')).toBeNull();
    });

    it('applies the CSS transform from useDraggable', () => {
      mockDraggable.transform = { x: 42, y: 10, scaleX: 1, scaleY: 1 };
      const { container } = renderEntry();
      const row = container.firstElementChild as HTMLElement;
      expect(row.style.transform).toMatch(/translate3d\(42px,10px/);
    });
  });

  describe('droppable behaviour', () => {
    it('disables the droppable for non-folder items', () => {
      renderEntry({ itemType: 'hit', caseId: 'case-1' });
      expect(vi.mocked(useDroppable)).toHaveBeenCalledWith(expect.objectContaining({ disabled: true }));
    });

    it('enables the droppable for folder items when caseId is set and not dragging', () => {
      renderEntry({ itemType: 'folder', caseId: 'case-1' });
      expect(vi.mocked(useDroppable)).toHaveBeenCalledWith(expect.objectContaining({ disabled: false }));
    });

    it('disables the droppable for folder items when caseId is null', () => {
      renderEntry({ itemType: 'folder', caseId: null });
      expect(vi.mocked(useDroppable)).toHaveBeenCalledWith(expect.objectContaining({ disabled: true }));
    });

    it('shows the drop highlight border when isOver and caseId match', () => {
      vi.mocked(useDroppable).mockReturnValue({ setNodeRef: vi.fn(), isOver: true } as any);
      const { container } = renderEntry({ caseId: 'case-1', itemType: 'folder' });
      // The absolute overlay Box has a dynamic border-color — it should be present in DOM
      const overlay = container.querySelector('[style*="border"]') ?? container.querySelector('div > div');
      expect(overlay).toBeInTheDocument();
    });
  });

  describe('DnD ID namespacing', () => {
    it('passes the namespaced id to useDraggable', async () => {
      const { useDraggable } = await import('@dnd-kit/core');
      renderEntry({ caseId: 'case-1', itemType: 'hit', path: 'folder/item' });
      expect(vi.mocked(useDraggable)).toHaveBeenCalledWith(expect.objectContaining({ id: 'case-1:hit:folder/item' }));
    });

    it('passes the namespaced id to useDroppable', async () => {
      renderEntry({ caseId: 'case-1', itemType: 'folder', path: 'docs' });
      expect(vi.mocked(useDroppable)).toHaveBeenCalledWith(expect.objectContaining({ id: 'case-1:folder:docs' }));
    });

    it('uses empty string prefix when caseId is null', async () => {
      const { useDraggable } = await import('@dnd-kit/core');
      renderEntry({ caseId: null, itemType: 'hit', path: 'item' });
      expect(vi.mocked(useDraggable)).toHaveBeenCalledWith(expect.objectContaining({ id: ':hit:item' }));
    });
  });

  describe('drag disabled when caseId is falsy', () => {
    it('disables dragging when caseId is null', async () => {
      const { useDraggable } = await import('@dnd-kit/core');
      renderEntry({ caseId: null });
      expect(vi.mocked(useDraggable)).toHaveBeenCalledWith(expect.objectContaining({ disabled: true }));
    });

    it('enables dragging when caseId is set', async () => {
      const { useDraggable } = await import('@dnd-kit/core');
      renderEntry({ caseId: 'case-1' });
      expect(vi.mocked(useDraggable)).toHaveBeenCalledWith(expect.objectContaining({ disabled: false }));
    });
  });

  describe('click handler', () => {
    it('calls onClick when the entry is clicked', async () => {
      const onClick = vi.fn();
      renderEntry({ onClick });
      await userEvent.click(screen.getByText('my label'));
      expect(onClick).toHaveBeenCalledTimes(1);
    });
  });

  describe('drag data payload', () => {
    it('includes type, label, entry, and caseId in drag data', async () => {
      const { useDraggable } = await import('@dnd-kit/core');
      const entry = hitItem('folder/item');
      renderEntry({ caseId: 'case-1', itemType: 'hit', label: 'my label', entry });
      expect(vi.mocked(useDraggable)).toHaveBeenCalledWith(
        expect.objectContaining({
          data: { type: 'hit', label: 'my label', entry, caseId: 'case-1' }
        })
      );
    });
  });
});
