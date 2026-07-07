import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { Case } from 'models/entities/generated/Case';
import type { Task } from 'models/entities/generated/Task';
import { MemoryRouter } from 'react-router-dom';
import { createMockCase } from 'tests/utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Hoisted mocks
// ---------------------------------------------------------------------------

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockCaseGet = vi.hoisted(() => vi.fn());

/** Accumulated CaseTask render props — reset in beforeEach. */
const mockCaseTaskProps = vi.hoisted(() => ({ current: [] as any[] }));

/** Captures the Autocomplete onChange so tests can call it directly. */
const mockAutocompleteOnChange = vi.hoisted(() => ({ fn: null as ((e: any, val: string[]) => void) | null }));

// ---------------------------------------------------------------------------
// Module-level mocks
// ---------------------------------------------------------------------------

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('api', () => ({
  default: {
    v2: {
      case: {
        get: (id: string) => mockCaseGet(id),
        put: vi.fn()
      }
    }
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

// Stub CaseTask to avoid heavy rendering while capturing props for inspection.
vi.mock('./CaseTask', () => ({
  default: (props: any) => {
    mockCaseTaskProps.current.push(props);
    return (
      <div
        id={props.newTask ? 'case-task-new' : `case-task-${props.task?.id ?? 'unknown'}`}
        data-readonly={String(!!props.readOnly)}
        data-task-id={props.task?.id ?? ''}
        data-case-origin-id={props.caseOrigin?.caseId ?? ''}
      />
    );
  }
}));

// Stub Autocomplete to capture onChange and render selected values as queryable spans.
vi.mock('@mui/material', async () => {
  const actual = await vi.importActual('@mui/material');
  return {
    ...actual,
    Autocomplete: ({ onChange, value }: any) => {
      mockAutocompleteOnChange.fn = onChange;
      return (
        <div id="child-case-autocomplete">
          {(value ?? []).map((v: string) => (
            <span key={v} id={`selected-${v}`}>
              {v}
            </span>
          ))}
        </div>
      );
    }
  };
});

// ---------------------------------------------------------------------------
// Imports after mocks
// ---------------------------------------------------------------------------

import TaskPanel from './TaskPanel';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mkTask = (id: string, summary = 'Task summary'): Task => ({
  id,
  summary,
  complete: false
});

const renderPanel = (caseOverrides?: Partial<Case>, updateCase = vi.fn().mockResolvedValue(undefined)) => {
  const _case = createMockCase({ tasks: [], items: [], ...caseOverrides });
  render(
    <MemoryRouter>
      <TaskPanel case={_case} updateCase={updateCase} />
    </MemoryRouter>
  );
  return { _case, updateCase };
};

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  mockDispatchApi.mockReset();
  mockCaseGet.mockReset();
  mockCaseTaskProps.current = [];
  mockAutocompleteOnChange.fn = null;
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('TaskPanel', () => {
  describe('structure', () => {
    it('renders the tasks heading', () => {
      renderPanel();
      expect(screen.getByText('page.cases.dashboard.tasks')).toBeInTheDocument();
    });

    it('renders the add-task area', () => {
      renderPanel();
      expect(screen.getByText('page.cases.dashboard.tasks.add')).toBeInTheDocument();
    });

    it('does not show child-case controls when there are no case-type items', () => {
      renderPanel({ items: [{ type: 'hit', value: 'h1' }] });
      expect(screen.queryByTestId('child-case-autocomplete')).not.toBeInTheDocument();
    });

    it('does not show child-case controls when items array is empty', () => {
      renderPanel({ items: [] });
      expect(screen.queryByTestId('child-case-autocomplete')).not.toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  describe('parent tasks', () => {
    it('renders a CaseTask for each task on the parent case', () => {
      renderPanel({ tasks: [mkTask('t1', 'First'), mkTask('t2', 'Second')] });
      expect(screen.getByTestId('case-task-t1')).toBeInTheDocument();
      expect(screen.getByTestId('case-task-t2')).toBeInTheDocument();
    });

    it('passes only non-null item paths to CaseTask', () => {
      renderPanel({
        tasks: [mkTask('t1')],
        items: [
          { type: 'hit', value: 'h1' },
          { type: 'hit', value: 'h2' }
        ]
      });
      const captured = mockCaseTaskProps.current.find((p: any) => p.task?.id === 't1');
      expect(captured.paths).toEqual(['root/h1']);
    });

    it('calls updateCase with merged task fields on onEdit', async () => {
      const { updateCase } = renderPanel({ tasks: [mkTask('t1', 'Original')] });
      const captured = mockCaseTaskProps.current.find((p: any) => p.task?.id === 't1');
      await act(() => captured.onEdit({ summary: 'Updated' }));
      expect(updateCase).toHaveBeenCalledWith(
        expect.objectContaining({
          tasks: expect.arrayContaining([expect.objectContaining({ id: 't1', summary: 'Updated' })])
        })
      );
    });

    it('preserves unmodified fields of other tasks when one task is edited', async () => {
      const { updateCase } = renderPanel({
        tasks: [mkTask('t1', 'Original'), mkTask('t2', 'Sibling')]
      });
      const captured = mockCaseTaskProps.current.find((p: any) => p.task?.id === 't1');
      await act(() => captured.onEdit({ complete: true }));
      const callArg = (updateCase as ReturnType<typeof vi.fn>).mock.calls[0][0];
      expect(callArg.tasks.find((t: Task) => t.id === 't2')).toBeDefined();
    });

    it('preserves other fields of the edited task when onEdit is called with a partial update', async () => {
      const { updateCase } = renderPanel({ tasks: [mkTask('t1', 'Original')] });
      const captured = mockCaseTaskProps.current.find((p: any) => p.task?.id === 't1');
      await act(() => captured.onEdit({ complete: true }));
      expect(updateCase).toHaveBeenCalledWith(
        expect.objectContaining({
          tasks: expect.arrayContaining([expect.objectContaining({ id: 't1', summary: 'Original', complete: true })])
        })
      );
    });

    it('calls updateCase excluding the deleted task on onDelete', async () => {
      const tasks = [mkTask('t1', 'Delete me'), mkTask('t2', 'Keep me')];
      const { updateCase } = renderPanel({ tasks });
      const captured = mockCaseTaskProps.current.find((p: any) => p.task?.id === 't1');
      await act(() => captured.onDelete());
      const callArg = (updateCase as ReturnType<typeof vi.fn>).mock.calls[0][0];
      expect(callArg.tasks.find((t: Task) => t.id === 't1')).toBeUndefined();
      expect(callArg.tasks.find((t: Task) => t.id === 't2')).toBeDefined();
    });
  });

  // -------------------------------------------------------------------------
  describe('add task', () => {
    it('shows a new CaseTask form after clicking the add-task area', () => {
      renderPanel();
      fireEvent.click(screen.getByText('page.cases.dashboard.tasks.add'));
      expect(screen.getByTestId('case-task-new')).toBeInTheDocument();
    });

    it('calls updateCase with the new task on save and hides the form', async () => {
      const { updateCase } = renderPanel();
      fireEvent.click(screen.getByText('page.cases.dashboard.tasks.add'));
      const captured = mockCaseTaskProps.current.find((p: any) => p.newTask);
      await act(() => captured.onEdit({ summary: 'Brand new task', complete: false }));
      expect(updateCase).toHaveBeenCalledWith(
        expect.objectContaining({
          tasks: expect.arrayContaining([expect.objectContaining({ summary: 'Brand new task' })])
        })
      );
      await waitFor(() => {
        expect(screen.queryByTestId('case-task-new')).not.toBeInTheDocument();
      });
    });

    it('hides the new task form when onDelete is called on the new CaseTask', async () => {
      renderPanel();
      fireEvent.click(screen.getByText('page.cases.dashboard.tasks.add'));
      const captured = mockCaseTaskProps.current.find((p: any) => p.newTask);
      await act(() => captured.onDelete());
      await waitFor(() => {
        expect(screen.queryByTestId('case-task-new')).not.toBeInTheDocument();
      });
    });

    it('appends the new task to the existing tasks list', async () => {
      const { updateCase } = renderPanel({ tasks: [mkTask('t1', 'Existing')] });
      fireEvent.click(screen.getByText('page.cases.dashboard.tasks.add'));
      const captured = mockCaseTaskProps.current.find((p: any) => p.newTask);
      await act(() => captured.onEdit({ summary: 'New task' }));
      const callArg = (updateCase as ReturnType<typeof vi.fn>).mock.calls[0][0];
      expect(callArg.tasks).toHaveLength(2);
    });
  });

  // -------------------------------------------------------------------------
  describe('child case aggregation', () => {
    const mkChildCase = (id: string, title: string, taskList: Task[] = [], itemPaths: string[] = []) =>
      createMockCase({
        case_id: id,
        title,
        tasks: taskList,
        items: itemPaths.map(p => ({ type: 'hit', value: p }))
      });

    const setupChild = (child: Case) => {
      mockCaseGet.mockReturnValue(Promise.resolve(child));
      mockDispatchApi.mockImplementation((p: any) => p);
    };

    it('fetches child cases for items of type "case"', async () => {
      setupChild(mkChildCase('child-1', 'Child One'));
      renderPanel({ items: [{ type: 'case', value: 'child-1' }] });
      await waitFor(() => {
        expect(mockCaseGet).toHaveBeenCalledWith('child-1');
      });
    });

    it('does not fetch child cases for non-case item types', async () => {
      setupChild(mkChildCase('child-1', 'Child One'));
      renderPanel({ items: [{ type: 'hit', value: 'child-1' }] });
      await new Promise(r => setTimeout(r, 0));
      expect(mockCaseGet).not.toHaveBeenCalled();
    });

    it('renders a section with the child case name after fetch', async () => {
      setupChild(mkChildCase('child-1', 'Child One'));
      renderPanel({ items: [{ type: 'case', value: 'child-1' }] });
      await waitFor(() => {
        expect(screen.getByText('Child One')).toBeInTheDocument();
      });
    });

    it('selects all fetched child cases by default in the autocomplete', async () => {
      const child1 = mkChildCase('child-1', 'Child One');
      const child2 = mkChildCase('child-2', 'Child Two');
      mockCaseGet.mockImplementation((id: string) => Promise.resolve(id === 'child-1' ? child1 : child2));
      mockDispatchApi.mockImplementation((p: any) => p);

      renderPanel({
        items: [
          { type: 'case', value: 'child-1' },
          { type: 'case', value: 'child-2' }
        ]
      });

      await waitFor(() => {
        expect(screen.getByTestId('selected-child-1')).toBeInTheDocument();
        expect(screen.getByTestId('selected-child-2')).toBeInTheDocument();
      });
    });

    it('filters out child cases where dispatchApi returns null', async () => {
      mockCaseGet.mockReturnValue(Promise.resolve(null));
      mockDispatchApi.mockResolvedValue(null);

      renderPanel({ items: [{ type: 'case', value: 'missing' }] });

      await waitFor(() => {
        expect(mockDispatchApi).toHaveBeenCalled();
      });
      expect(screen.queryByTestId('child-case-autocomplete')).not.toBeInTheDocument();
    });

    it('fetches at most MAX_CHILD_CASES (10) child cases when more are present', async () => {
      const items = Array.from({ length: 12 }, (_, i) => ({
        type: 'case',
        value: `c${i}`
      }));
      mockCaseGet.mockImplementation((id: string) => Promise.resolve(mkChildCase(id, `Case ${id}`)));
      mockDispatchApi.mockImplementation((p: any) => p);

      renderPanel({ items });

      await waitFor(() => {
        expect(mockCaseGet).toHaveBeenCalledTimes(10);
      });
    });

    it('renders child case tasks with readOnly=true', async () => {
      const childTask = mkTask('ct1', 'Child Task');
      setupChild(mkChildCase('child-1', 'Child One', [childTask]));
      renderPanel({ items: [{ type: 'case', value: 'child-1' }] });

      await waitFor(() => {
        const captured = mockCaseTaskProps.current.find((p: any) => p.task?.id === 'ct1');
        expect(captured).toBeDefined();
        expect(captured.readOnly).toBe(true);
      });
    });

    it('passes caseOrigin to each child case CaseTask', async () => {
      const childTask = mkTask('ct1', 'Child Task');
      setupChild(mkChildCase('child-1', 'Child One', [childTask]));
      renderPanel({ items: [{ type: 'case', value: 'child-1' }] });

      await waitFor(() => {
        const captured = mockCaseTaskProps.current.find((p: any) => p.task?.id === 'ct1');
        expect(captured.caseOrigin).toEqual({ caseId: 'child-1', caseName: 'Child One' });
      });
    });

    it('passes non-null paths from child case items to each child CaseTask', async () => {
      const childTask = mkTask('ct1', 'Child Task');
      const child = createMockCase({
        case_id: 'child-1',
        title: 'Child One',
        tasks: [childTask],
        items: [
          { type: 'hit', value: 'h1' },
          { type: 'hit', value: 'h2' }
        ]
      });
      mockCaseGet.mockReturnValue(Promise.resolve(child));
      mockDispatchApi.mockImplementation((p: any) => p);
      renderPanel({ items: [{ type: 'case', value: 'child-1' }] });

      await waitFor(() => {
        const captured = mockCaseTaskProps.current.find((p: any) => p.task?.id === 'ct1');
        expect(captured.paths).toEqual(['child-1/hit']);
      });
    });

    it('shows an empty message when the child case has no tasks', async () => {
      setupChild(mkChildCase('child-1', 'Child One', []));
      renderPanel({ items: [{ type: 'case', value: 'child-1' }] });
      await waitFor(() => {
        expect(screen.getByText('page.cases.dashboard.tasks.child.empty')).toBeInTheDocument();
      });
    });

    it('links the child case section chip to /cases/{caseId}', async () => {
      setupChild(mkChildCase('child-1', 'Child One', []));
      renderPanel({ items: [{ type: 'case', value: 'child-1' }] });
      await waitFor(() => {
        const link = screen.getByText('Child One').closest('a');
        expect(link).toHaveAttribute('href', '/cases/child-1');
      });
    });

    it('uses the case title as the child case name when title is set', async () => {
      setupChild(mkChildCase('child-1', 'My Child Case', []));
      renderPanel({ items: [{ type: 'case', value: 'child-1' }] });
      await waitFor(() => {
        expect(screen.getByText('My Child Case')).toBeInTheDocument();
      });
    });
  });

  // -------------------------------------------------------------------------
  describe('child task visibility toggle', () => {
    const buildAndRender = async (taskList: Task[]) => {
      const child = createMockCase({
        case_id: 'child-1',
        title: 'Child One',
        tasks: taskList,
        items: []
      });
      mockCaseGet.mockReturnValue(Promise.resolve(child));
      mockDispatchApi.mockImplementation((p: any) => p);
      renderPanel({ items: [{ type: 'case', value: 'child-1' }] });
      await waitFor(() => screen.getByText('Child One'));
    };

    it('shows child tasks by default', async () => {
      await buildAndRender([mkTask('ct1', 'Child Task')]);
      expect(screen.getByTestId('case-task-ct1')).toBeInTheDocument();
    });

    it('hides child tasks after clicking the toggle chip', async () => {
      await buildAndRender([mkTask('ct1', 'Child Task')]);
      fireEvent.click(screen.getByText('page.cases.dashboard.tasks.child_cases'));
      await waitFor(() => {
        expect(screen.queryByTestId('case-task-ct1')).not.toBeInTheDocument();
      });
    });

    it('re-shows child tasks after toggling the chip twice', async () => {
      await buildAndRender([mkTask('ct1', 'Child Task')]);
      const chip = screen.getByText('page.cases.dashboard.tasks.child_cases');
      fireEvent.click(chip);
      fireEvent.click(chip);
      await waitFor(() => {
        expect(screen.getByTestId('case-task-ct1')).toBeInTheDocument();
      });
    });

    it('also hides the empty-task message when toggled off', async () => {
      await buildAndRender([]);
      fireEvent.click(screen.getByText('page.cases.dashboard.tasks.child_cases'));
      await waitFor(() => {
        expect(screen.queryByText('page.cases.dashboard.tasks.child.empty')).not.toBeInTheDocument();
      });
    });
  });

  // -------------------------------------------------------------------------
  describe('child case filter via autocomplete', () => {
    it('hides a child case section when it is deselected via autocomplete onChange', async () => {
      const childTask = mkTask('ct1', 'Child Task');
      const child = createMockCase({
        case_id: 'child-1',
        title: 'Child One',
        tasks: [childTask],
        items: []
      });
      mockCaseGet.mockReturnValue(Promise.resolve(child));
      mockDispatchApi.mockImplementation((p: any) => p);

      renderPanel({ items: [{ type: 'case', value: 'child-1' }] });
      await waitFor(() => screen.getByTestId('case-task-ct1'));

      act(() => {
        mockAutocompleteOnChange.fn?.({} as any, []);
      });

      await waitFor(() => {
        expect(screen.queryByTestId('case-task-ct1')).not.toBeInTheDocument();
      });
    });

    it('shows a child case section when it is re-selected after deselection', async () => {
      const childTask = mkTask('ct1', 'Child Task');
      const child = createMockCase({
        case_id: 'child-1',
        title: 'Child One',
        tasks: [childTask],
        items: []
      });
      mockCaseGet.mockReturnValue(Promise.resolve(child));
      mockDispatchApi.mockImplementation((p: any) => p);

      renderPanel({ items: [{ type: 'case', value: 'child-1' }] });
      await waitFor(() => screen.getByTestId('case-task-ct1'));

      act(() => {
        mockAutocompleteOnChange.fn?.({} as any, []);
      });
      act(() => {
        mockAutocompleteOnChange.fn?.({} as any, ['child-1']);
      });

      await waitFor(() => {
        expect(screen.getByTestId('case-task-ct1')).toBeInTheDocument();
      });
    });
  });

  // -------------------------------------------------------------------------
  describe('skeleton when case is null', () => {
    it('renders a Skeleton and not the task heading when case is null', () => {
      const { container } = render(
        <MemoryRouter>
          <TaskPanel case={null as any} updateCase={vi.fn()} />
        </MemoryRouter>
      );
      expect(container.querySelector('.MuiSkeleton-root')).toBeInTheDocument();
      expect(screen.queryByText('page.cases.dashboard.tasks')).not.toBeInTheDocument();
    });
  });
});
