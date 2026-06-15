import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { Task } from 'models/entities/generated/Task';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Hoisted mocks
// ---------------------------------------------------------------------------

/** Captures the UserList onChange so tests can simulate assignment changes. */
const mockUserListOnChange = vi.hoisted(() => ({ fn: null as ((vals: (string | undefined)[]) => void) | null }));

/** Captures the path Autocomplete onChange so tests can simulate path selection. */
const mockPathAutocompleteOnChange = vi.hoisted(() => ({ fn: null as ((e: any, val: string | null) => void) | null }));

// ---------------------------------------------------------------------------
// Module-level mocks
// ---------------------------------------------------------------------------

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

// Stub Autocomplete to avoid complex JSDOM interaction; exposes onChange directly.
vi.mock('@mui/material', async () => {
  const actual = await vi.importActual('@mui/material');
  return {
    ...actual,
    Autocomplete: ({ onChange, value }: any) => {
      mockPathAutocompleteOnChange.fn = onChange;
      return <div id="path-autocomplete" data-value={value ?? ''} />;
    }
  };
});

// ---------------------------------------------------------------------------
// Imports after mocks
// ---------------------------------------------------------------------------

import CaseTask from './CaseTask';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mkTask = (overrides?: Partial<Task>): Task => ({
  id: 't1',
  summary: 'Test task',
  complete: false,
  path: undefined,
  assignment: undefined,
  ...overrides
});

interface RenderOptions {
  paths?: string[];
  readOnly?: boolean;
  newTask?: boolean;
  caseOrigin?: { caseId: string; caseName: string };
}

const renderTask = (task?: Task, opts: RenderOptions = {}) => {
  const mockOnEdit = vi.fn().mockResolvedValue(undefined);
  const mockOnDelete = vi.fn().mockResolvedValue(undefined);
  const { container } = render(
    <MemoryRouter>
      <CaseTask
        task={task}
        paths={opts.paths ?? []}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
        readOnly={opts.readOnly}
        newTask={opts.newTask}
        caseOrigin={opts.caseOrigin}
      />
    </MemoryRouter>
  );
  return { container, mockOnEdit, mockOnDelete };
};

// Query helpers — MUI icons render SVGs with data-testid set by the icon name.
// Use `?? null` so a missing element resolves to null rather than undefined;
// jest-dom's toBeInTheDocument accepts null but not undefined.
const getEditButton = (container: HTMLElement) =>
  (container.querySelector('[data-testid="EditIcon"]')?.closest('button') ?? null) as HTMLElement | null;

const getSaveButton = (container: HTMLElement) =>
  (container.querySelector('[data-testid="CheckIcon"]')?.closest('button') ?? null) as HTMLElement | null;

const getCancelButton = (container: HTMLElement) =>
  (container.querySelector('[data-testid="CloseIcon"]')?.closest('button') ?? null) as HTMLElement | null;

const getDeleteButton = (container: HTMLElement) =>
  (container.querySelector('[data-testid="DeleteIcon"]')?.closest('button') ?? null) as HTMLElement | null;

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  mockUserListOnChange.fn = null;
  mockPathAutocompleteOnChange.fn = null;
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('CaseTask', () => {
  // -------------------------------------------------------------------------
  describe('display mode', () => {
    it('renders the task summary text', () => {
      renderTask(mkTask({ summary: 'My important task' }));
      expect(screen.getByText('My important task')).toBeInTheDocument();
    });

    it('shows a checked checkbox when task.complete is true', () => {
      renderTask(mkTask({ complete: true }));
      expect(screen.getByRole('checkbox')).toBeChecked();
    });

    it('shows an unchecked checkbox when task.complete is false', () => {
      renderTask(mkTask({ complete: false }));
      expect(screen.getByRole('checkbox')).not.toBeChecked();
    });

    it('shows a path chip linking to the path when task.path is set', () => {
      renderTask(mkTask({ path: 'root/evidence' }));
      const link = screen.getByText('root/evidence').closest('a');
      expect(link).toHaveAttribute('href', 'root/evidence');
    });

    it('does not show a path chip when task.path is null', () => {
      renderTask(mkTask({ path: undefined }));
      // Path chip is the only Link rendered when no caseOrigin is provided
      expect(screen.queryByRole('link')).not.toBeInTheDocument();
    });

    it('shows the edit button in display mode', () => {
      const { container } = renderTask(mkTask());
      expect(getEditButton(container)).toBeInTheDocument();
    });

    it('does not show delete or cancel buttons in display mode', () => {
      const { container } = renderTask(mkTask());
      expect(getDeleteButton(container)).not.toBeInTheDocument();
      expect(getCancelButton(container)).not.toBeInTheDocument();
    });

    it('does not show the save button in display mode', () => {
      const { container } = renderTask(mkTask());
      expect(getSaveButton(container)).not.toBeInTheDocument();
    });

    it('renders the UserList component', () => {
      renderTask(mkTask());
      expect(screen.getByTestId('user-list')).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  describe('origin chip', () => {
    it('renders a chip linking to the source case when caseOrigin is provided', () => {
      renderTask(mkTask(), { caseOrigin: { caseId: 'src-case', caseName: 'Source Case' } });
      const chip = screen.getByText('Source Case').closest('a');
      expect(chip).toHaveAttribute('href', '/cases/src-case');
    });

    it('does not render an origin chip when caseOrigin is not provided', () => {
      renderTask(mkTask({ summary: 'No origin' }));
      expect(screen.queryByRole('link')).not.toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  describe('edit mode', () => {
    it('enters edit mode and shows a textbox when the edit button is clicked', () => {
      const { container } = renderTask(mkTask());
      fireEvent.click(getEditButton(container)!);
      expect(screen.getByRole('textbox')).toBeInTheDocument();
    });

    it('shows a save (check) button after entering edit mode', () => {
      const { container } = renderTask(mkTask());
      fireEvent.click(getEditButton(container)!);
      expect(getSaveButton(container)).toBeInTheDocument();
    });

    it('shows a cancel button in edit mode', () => {
      const { container } = renderTask(mkTask());
      fireEvent.click(getEditButton(container)!);
      expect(getCancelButton(container)).toBeInTheDocument();
    });

    it('shows a delete button in edit mode for existing tasks', () => {
      const { container } = renderTask(mkTask());
      fireEvent.click(getEditButton(container)!);
      expect(getDeleteButton(container)).toBeInTheDocument();
    });

    it('the save button is disabled when the summary is cleared', () => {
      const { container } = renderTask(mkTask({ summary: 'Has text' }));
      fireEvent.click(getEditButton(container)!);
      fireEvent.change(screen.getByRole('textbox'), { target: { value: '' } });
      expect(getSaveButton(container)).toBeDisabled();
    });

    it('the save button is disabled when nothing has changed (not dirty)', () => {
      const { container } = renderTask(mkTask({ summary: 'Unchanged' }));
      fireEvent.click(getEditButton(container)!);
      // No changes made — not dirty
      expect(getSaveButton(container)).toBeDisabled();
    });

    it('enables the save button after the summary is changed', () => {
      const { container } = renderTask(mkTask({ summary: 'Original' }));
      fireEvent.click(getEditButton(container)!);
      fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Changed' } });
      expect(getSaveButton(container)).not.toBeDisabled();
    });

    it('calls onEdit with the updated fields and exits edit mode on save', async () => {
      const { container, mockOnEdit } = renderTask(mkTask({ summary: 'Original' }));
      fireEvent.click(getEditButton(container)!);
      fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Updated summary' } });
      await act(() => fireEvent.click(getSaveButton(container)!));
      expect(mockOnEdit).toHaveBeenCalledWith(expect.objectContaining({ summary: 'Updated summary' }));
      await waitFor(() => {
        expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
      });
    });

    it('exits edit mode and shows the original summary on cancel', () => {
      const { container } = renderTask(mkTask({ summary: 'Original' }));
      fireEvent.click(getEditButton(container)!);
      fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Changed' } });
      fireEvent.click(getCancelButton(container)!);
      expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
      // task?.summary || summary — original task prop wins when not editing
      expect(screen.getByText('Original')).toBeInTheDocument();
    });

    it('calls onDelete when the delete button is clicked', async () => {
      const { container, mockOnDelete } = renderTask(mkTask());
      fireEvent.click(getEditButton(container)!);
      await act(() => fireEvent.click(getDeleteButton(container)!));
      expect(mockOnDelete).toHaveBeenCalled();
    });

    it('shows the path Autocomplete in edit mode', () => {
      const { container } = renderTask(mkTask(), { paths: ['root/path'] });
      fireEvent.click(getEditButton(container)!);
      expect(screen.getByTestId('path-autocomplete')).toBeInTheDocument();
    });

    it('updates the Autocomplete value when a path is selected', () => {
      const { container } = renderTask(mkTask(), { paths: ['root/path'] });
      fireEvent.click(getEditButton(container)!);
      act(() => {
        mockPathAutocompleteOnChange.fn?.({} as any, 'root/path');
      });
      expect(screen.getByTestId('path-autocomplete')).toHaveAttribute('data-value', 'root/path');
    });

    it('includes the selected path in the onEdit payload on save', async () => {
      const { container, mockOnEdit } = renderTask(mkTask({ summary: 'Task' }), {
        paths: ['root/path']
      });
      fireEvent.click(getEditButton(container)!);
      act(() => {
        mockPathAutocompleteOnChange.fn?.({} as any, 'root/path');
      });
      await act(() => fireEvent.click(getSaveButton(container)!));
      expect(mockOnEdit).toHaveBeenCalledWith(expect.objectContaining({ path: 'root/path' }));
    });
  });

  // -------------------------------------------------------------------------
  describe('new task mode', () => {
    it('starts in edit mode (textbox visible immediately)', () => {
      renderTask(undefined, { newTask: true });
      expect(screen.getByRole('textbox')).toBeInTheDocument();
    });

    it('does not show a delete button for a new task', () => {
      const { container } = renderTask(undefined, { newTask: true });
      expect(getDeleteButton(container)).not.toBeInTheDocument();
    });

    it('calls onDelete (cancels) when cancel is clicked on a new task', async () => {
      const { container, mockOnDelete } = renderTask(undefined, { newTask: true });
      await act(() => fireEvent.click(getCancelButton(container)!));
      expect(mockOnDelete).toHaveBeenCalled();
    });

    it('calls onEdit with the entered summary when the new task is saved', async () => {
      const { container, mockOnEdit } = renderTask(undefined, { newTask: true });
      fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Brand new task' } });
      await act(() => fireEvent.click(getSaveButton(container)!));
      expect(mockOnEdit).toHaveBeenCalledWith(expect.objectContaining({ summary: 'Brand new task' }));
    });

    it('disables the save button when summary is empty on a new task', () => {
      const { container } = renderTask(undefined, { newTask: true });
      expect(getSaveButton(container)).toBeDisabled();
    });
  });

  // -------------------------------------------------------------------------
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

    it('does not auto-call onEdit for complete changes when readOnly', async () => {
      // The checkbox is disabled in readOnly — clicking it has no effect.
      const { mockOnEdit } = renderTask(mkTask({ complete: false }), { readOnly: true });
      fireEvent.click(screen.getByRole('checkbox'));
      await new Promise(r => setTimeout(r, 0));
      expect(mockOnEdit).not.toHaveBeenCalled();
    });

    it('does not auto-call onEdit for assignment changes when readOnly', async () => {
      // CaseTask guards setAssignment with !readOnly in the onChange inline function.
      const { mockOnEdit } = renderTask(mkTask({ assignment: undefined }), { readOnly: true });
      act(() => {
        mockUserListOnChange.fn?.(['user-42']);
      });
      await new Promise(r => setTimeout(r, 0));
      expect(mockOnEdit).not.toHaveBeenCalled();
    });

    it('does not auto-call onEdit when complete is unchanged (initial render)', async () => {
      const { mockOnEdit } = renderTask(mkTask({ complete: false }));
      await new Promise(r => setTimeout(r, 0));
      expect(mockOnEdit).not.toHaveBeenCalled();
    });
  });

  // -------------------------------------------------------------------------
  describe('read-only mode', () => {
    it('hides the edit button', () => {
      const { container } = renderTask(mkTask(), { readOnly: true });
      expect(getEditButton(container)).not.toBeInTheDocument();
    });

    it('hides the delete button', () => {
      const { container } = renderTask(mkTask(), { readOnly: true });
      expect(getDeleteButton(container)).not.toBeInTheDocument();
    });

    it('hides the cancel button', () => {
      const { container } = renderTask(mkTask(), { readOnly: true });
      expect(getCancelButton(container)).not.toBeInTheDocument();
    });

    it('disables the checkbox', () => {
      renderTask(mkTask(), { readOnly: true });
      expect(screen.getByRole('checkbox')).toBeDisabled();
    });

    it('marks the UserList as disabled', () => {
      renderTask(mkTask(), { readOnly: true });
      expect(screen.getByTestId('user-list')).toHaveAttribute('data-disabled', 'true');
    });

    it('still renders the task summary text', () => {
      renderTask(mkTask({ summary: 'Read-only task' }), { readOnly: true });
      expect(screen.getByText('Read-only task')).toBeInTheDocument();
    });

    it('still renders the origin chip when caseOrigin is provided', () => {
      renderTask(mkTask(), {
        readOnly: true,
        caseOrigin: { caseId: 'src', caseName: 'Src Case' }
      });
      expect(screen.getByText('Src Case')).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  describe('task prop sync effect', () => {
    it('syncs local state when the task prop changes externally', () => {
      const task = mkTask({ summary: 'Original' });
      const { rerender } = render(
        <MemoryRouter>
          <CaseTask task={task} paths={[]} onEdit={vi.fn()} onDelete={vi.fn()} />
        </MemoryRouter>
      );
      // Component shows original summary
      expect(screen.getByText('Original')).toBeInTheDocument();

      const updatedTask = mkTask({ summary: 'Updated externally' });
      rerender(
        <MemoryRouter>
          <CaseTask task={updatedTask} paths={[]} onEdit={vi.fn()} onDelete={vi.fn()} />
        </MemoryRouter>
      );
      // After rerender with new task prop, display should update
      expect(screen.getByText('Updated externally')).toBeInTheDocument();
    });
  });
});
