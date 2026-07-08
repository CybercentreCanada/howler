import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { Task } from 'models/entities/generated/Task';
import { MemoryRouter } from 'react-router-dom';
import { createMockCase } from 'tests/utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockUserListOnChange = vi.hoisted(() => ({ fn: null as ((vals: (string | undefined)[]) => void) | null }));
const mockPathAutocompleteOnChange = vi.hoisted(() => ({ fn: null as ((e: unknown, val: any | null) => void) | null }));

vi.mock('components/elements/UserList', () => ({
  default: ({ onChange, userIds, disabled }: any) => {
    mockUserListOnChange.fn = onChange;
    return <div id="user-list" data-disabled={String(!!disabled)} data-user-ids={JSON.stringify(userIds)} />;
  }
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    Link: ({ to, children, ...props }: any) => (
      <a href={to} {...props}>
        {children}
      </a>
    )
  };
});

vi.mock('@mui/material', async () => {
  const actual = await vi.importActual('@mui/material');
  return {
    ...actual,
    Autocomplete: ({ onChange, value }: any) => {
      mockPathAutocompleteOnChange.fn = onChange;
      return <div id="path-autocomplete" data-value={value?.id ?? ''} />;
    }
  };
});

import CaseTask from './CaseTask';

const mkTask = (overrides?: Partial<Task>): Task => ({
  id: 't1',
  summary: 'Test task',
  complete: false,
  assignment: undefined,
  ...overrides
});

const testCase = createMockCase({
  case_id: 'case-1',
  items: [
    { id: 'root-folder', type: 'folder', value: 'Folder', name: 'Folder' },
    { id: 'item-1', type: 'hit', value: 'hit-1', name: 'Hit One', parent: 'root-folder' },
    { id: 'item-2', type: 'hit', value: 'hit-2', name: 'Hit Two' }
  ]
});

interface RenderOptions {
  readOnly?: boolean;
  newTask?: boolean;
}

const renderTask = (task?: Task, opts: RenderOptions = {}) => {
  const mockOnEdit = vi.fn().mockResolvedValue(undefined);
  const mockOnDelete = vi.fn().mockResolvedValue(undefined);
  const { container } = render(
    <MemoryRouter>
      <CaseTask
        case={testCase}
        task={task}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
        readOnly={opts.readOnly}
        newTask={opts.newTask}
      />
    </MemoryRouter>
  );
  return { container, mockOnEdit, mockOnDelete };
};

const getEditButton = (container: HTMLElement) =>
  (container.querySelector('[data-testid="EditIcon"]')?.closest('button') ?? null) as HTMLElement | null;

const getSaveButton = (container: HTMLElement) =>
  (container.querySelector('[data-testid="CheckIcon"]')?.closest('button') ?? null) as HTMLElement | null;

const getCancelButton = (container: HTMLElement) =>
  (container.querySelector('[data-testid="CloseIcon"]')?.closest('button') ?? null) as HTMLElement | null;

beforeEach(() => {
  mockUserListOnChange.fn = null;
  mockPathAutocompleteOnChange.fn = null;
});

describe('CaseTask', () => {
  describe('display mode', () => {
    it('renders the task summary text', () => {
      renderTask(mkTask({ summary: 'My important task' }));
      expect(screen.getByText('My important task')).toBeInTheDocument();
    });

    it('shows a checked checkbox when task.complete is true', () => {
      renderTask(mkTask({ complete: true }));
      expect(screen.getByRole('checkbox')).toBeChecked();
    });

    it('shows a path chip linking to the resolved item path when task.item is set', () => {
      renderTask(mkTask({ item: 'item-1' }));
      const link = screen.getByText('Hit One').closest('a');
      expect(link).toHaveAttribute('href', 'Folder/Hit One');
    });

    it('does not show an item chip when task.item is not set', () => {
      renderTask(mkTask({ item: undefined }));
      expect(screen.queryByRole('link')).not.toBeInTheDocument();
    });

    it('shows the edit button in display mode', () => {
      const { container } = renderTask(mkTask());
      expect(getEditButton(container)).toBeInTheDocument();
    });
  });

  describe('edit mode', () => {
    it('enters edit mode and shows a textbox when the edit button is clicked', () => {
      const { container } = renderTask(mkTask());
      fireEvent.click(getEditButton(container)!);
      expect(screen.getByRole('textbox')).toBeInTheDocument();
    });

    it('keeps save enabled after entering edit mode', () => {
      const { container } = renderTask(mkTask({ summary: 'Unchanged' }));
      fireEvent.click(getEditButton(container)!);
      expect(getSaveButton(container)).not.toBeDisabled();
    });

    it('calls onEdit with selected item id on save', async () => {
      const { container, mockOnEdit } = renderTask(mkTask({ summary: 'Task' }));
      fireEvent.click(getEditButton(container)!);
      act(() => {
        mockPathAutocompleteOnChange.fn?.({} as unknown, {
          id: 'item-2',
          type: 'hit',
          value: 'hit-2',
          name: 'Hit Two'
        });
      });
      await act(() => fireEvent.click(getSaveButton(container)!));
      expect(mockOnEdit).toHaveBeenCalledWith(expect.objectContaining({ item: 'item-2' }));
    });
  });

  describe('new task mode', () => {
    it('starts in edit mode and can be cancelled via onDelete', async () => {
      const { container, mockOnDelete } = renderTask(undefined, { newTask: true });
      expect(screen.getByRole('textbox')).toBeInTheDocument();
      await act(() => fireEvent.click(getCancelButton(container)!));
      expect(mockOnDelete).toHaveBeenCalled();
    });
  });

  describe('read-only mode', () => {
    it('hides edit controls and keeps checkbox disabled', () => {
      const { container } = renderTask(mkTask({ item: 'item-1' }), { readOnly: true });
      expect(getEditButton(container)).not.toBeInTheDocument();
      expect(screen.getByRole('checkbox')).toBeDisabled();
      expect(screen.getByText('Hit One')).toBeInTheDocument();
    });
  });

  describe('auto-update effects', () => {
    it('auto-calls onEdit when complete is toggled while not editing', async () => {
      const { mockOnEdit } = renderTask(mkTask({ complete: false }));
      await act(() => {
        fireEvent.click(screen.getByRole('checkbox'));
      });
      await waitFor(() => {
        expect(mockOnEdit).toHaveBeenCalledWith(expect.objectContaining({ complete: true }));
      });
    });

    it('auto-calls onEdit when assignment changes while not editing', async () => {
      const { mockOnEdit } = renderTask(mkTask({ assignment: undefined }));
      act(() => {
        mockUserListOnChange.fn?.(['user-42']);
      });
      await waitFor(() => {
        expect(mockOnEdit).toHaveBeenCalledWith(expect.objectContaining({ assignment: 'user-42' }));
      });
    });
  });
});
