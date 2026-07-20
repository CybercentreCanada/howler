import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { Case } from 'models/entities/generated/Case';
import type { Task } from 'models/entities/generated/Task';
import { MemoryRouter } from 'react-router-dom';
import { createMockCase } from 'tests/utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockCaseTaskProps = vi.hoisted(() => ({ current: [] as any[] }));
const mockAutocompleteOnChange = vi.hoisted(() => ({ fn: null as ((e: unknown, val: string[]) => void) | null }));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

const mockSearchPost = vi.hoisted(() => vi.fn());

vi.mock('api', () => ({
  default: {
    v2: {
      search: {
        post: (...args: any[]) => mockSearchPost(...args)
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

vi.mock('./CaseTask', () => ({
  default: (props: any) => {
    mockCaseTaskProps.current.push(props);
    return (
      <div
        id={props.newTask ? 'case-task-new' : `case-task-${props.task?.id ?? 'unknown'}`}
        data-readonly={String(!!props.readOnly)}
      />
    );
  }
}));

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

import TaskPanel from './TaskPanel';

const mkTask = (id: string, summary = 'Task summary'): Task => ({
  id,
  summary,
  complete: false
});

const renderPanel = (caseOverrides?: Partial<Case>, updateCase = vi.fn().mockResolvedValue(undefined)) => {
  const _case = createMockCase({ tasks: [], items: [], ...caseOverrides });
  const utils = render(
    <MemoryRouter>
      <TaskPanel case={_case} updateCase={updateCase} />
    </MemoryRouter>
  );
  return { _case, updateCase, ...utils };
};

beforeEach(() => {
  mockDispatchApi.mockReset();
  mockSearchPost.mockReset();
  mockCaseTaskProps.current = [];
  mockAutocompleteOnChange.fn = null;
});

describe('TaskPanel', () => {
  it('renders parent tasks as CaseTask entries', () => {
    const { container } = renderPanel({ tasks: [mkTask('t1'), mkTask('t2')] });
    expect(container.querySelector('#case-task-t1')).toBeInTheDocument();
    expect(container.querySelector('#case-task-t2')).toBeInTheDocument();
  });

  it('fetches child cases via v2 search when case-type items exist', async () => {
    const child = createMockCase({ case_id: 'child-1', title: 'Child One', tasks: [] });
    mockSearchPost.mockReturnValue('search-request');
    mockDispatchApi.mockResolvedValue({ items: [child] });

    renderPanel({ items: [{ type: 'case', value: 'child-1' }] });

    await waitFor(() => {
      expect(mockSearchPost).toHaveBeenCalledWith('case', { query: 'case_id:(child-1)' });
      expect(screen.getByText('Child One')).toBeInTheDocument();
    });
  });

  it('defaults autocomplete selection to all loaded child case ids', async () => {
    const child1 = createMockCase({ case_id: 'child-1', title: 'Child One', tasks: [] });
    const child2 = createMockCase({ case_id: 'child-2', title: 'Child Two', tasks: [] });
    mockSearchPost.mockReturnValue('search-request');
    mockDispatchApi.mockResolvedValue({ items: [child1, child2] });

    renderPanel({
      items: [
        { type: 'case', value: 'child-1' },
        { type: 'case', value: 'child-2' }
      ]
    });

    await waitFor(() => {
      expect(screen.getByText('child-1')).toBeInTheDocument();
      expect(screen.getByText('child-2')).toBeInTheDocument();
    });
  });

  it('renders child task entries as read-only', async () => {
    const childTask = mkTask('ct1', 'Child task');
    const child = createMockCase({ case_id: 'child-1', title: 'Child One', tasks: [childTask] });
    mockSearchPost.mockReturnValue('search-request');
    mockDispatchApi.mockResolvedValue({ items: [child] });

    renderPanel({ items: [{ type: 'case', value: 'child-1' }] });

    await waitFor(() => {
      const captured = mockCaseTaskProps.current.find((p: any) => p.task?.id === 'ct1');
      expect(captured?.readOnly).toBe(true);
      expect(captured?.case?.case_id).toBe('child-1');
    });
  });

  it('hides child section when deselected in autocomplete and restores on reselect', async () => {
    const childTask = mkTask('ct1', 'Child task');
    const child = createMockCase({ case_id: 'child-1', title: 'Child One', tasks: [childTask] });
    mockSearchPost.mockReturnValue('search-request');
    mockDispatchApi.mockResolvedValue({ items: [child] });

    renderPanel({ items: [{ type: 'case', value: 'child-1' }] });

    await waitFor(() => expect(document.querySelector('#case-task-ct1')).toBeInTheDocument());

    act(() => {
      mockAutocompleteOnChange.fn?.({} as unknown, []);
    });
    await waitFor(() => expect(document.querySelector('#case-task-ct1')).not.toBeInTheDocument());

    act(() => {
      mockAutocompleteOnChange.fn?.({} as unknown, ['child-1']);
    });
    await waitFor(() => expect(document.querySelector('#case-task-ct1')).toBeInTheDocument());
  });

  it('limits search to first 10 child case item values', async () => {
    const items = Array.from({ length: 12 }, (_, i) => ({ type: 'case', value: `c${i}` }));
    mockSearchPost.mockReturnValue('search-request');
    mockDispatchApi.mockResolvedValue({ items: [] });

    renderPanel({ items });

    await waitFor(() => {
      expect(mockSearchPost).toHaveBeenCalledWith('case', {
        query: 'case_id:(c0 OR c1 OR c2 OR c3 OR c4 OR c5 OR c6 OR c7 OR c8 OR c9)'
      });
    });
  });

  it('toggles child task visibility with the child-case chip', async () => {
    const childTask = mkTask('ct1', 'Child task');
    const child = createMockCase({ case_id: 'child-1', title: 'Child One', tasks: [childTask] });
    mockSearchPost.mockReturnValue('search-request');
    mockDispatchApi.mockResolvedValue({ items: [child] });

    renderPanel({ items: [{ type: 'case', value: 'child-1' }] });
    await waitFor(() => expect(document.querySelector('#case-task-ct1')).toBeInTheDocument());

    fireEvent.click(screen.getByText('page.cases.dashboard.tasks.child_cases'));
    await waitFor(() => expect(document.querySelector('#case-task-ct1')).not.toBeInTheDocument());

    fireEvent.click(screen.getByText('page.cases.dashboard.tasks.child_cases'));
    await waitFor(() => expect(document.querySelector('#case-task-ct1')).toBeInTheDocument());
  });
});
