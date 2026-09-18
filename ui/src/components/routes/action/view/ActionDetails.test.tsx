/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockShowSuccessMessage = vi.hoisted(() => vi.fn());
const mockExecuteAction = vi.hoisted(() => vi.fn());
const mockDeleteAction = vi.hoisted(() => vi.fn());
const mockOnSearch = vi.hoisted(() => vi.fn());
const mockSetLoading = vi.hoisted(() => vi.fn());
const mockPluginExecute = vi.hoisted(() => vi.fn(() => <div key="plugin-operation">plugin-operation</div>));

const modalContextToken = vi.hoisted(() => ({ name: 'modal-context' }));

vi.mock('@mui/icons-material', () => ({
  Delete: () => <div>delete-icon</div>,
  Edit: () => <div>edit-icon</div>,
  PlayCircleOutline: () => <div>play-icon</div>,
  Search: () => <div>search-icon</div>
}));

vi.mock('@mui/material', () => ({
  Button: ({ children, onClick, component: Component, to }: any) =>
    Component ? <a href={to}>{children}</a> : <button onClick={onClick}>{children}</button>,
  Checkbox: ({ name, onChange, checked }: any) => (
    <input type="checkbox" aria-label={name} checked={checked} onChange={e => onChange({ target: { name, checked: e.target.checked } })} />
  ),
  FormControlLabel: ({ control, label }: any) => <label>{control}{label}</label>,
  FormGroup: ({ children }: any) => <div>{children}</div>,
  IconButton: ({ children, onClick }: any) => <button onClick={onClick}>{children}</button>,
  LinearProgress: ({ value }: any) => <div>{`progress:${value ?? 'indeterminate'}`}</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('@tui/core', () => ({
  PageCenter: ({ children }: any) => <div>{children}</div>,
  useAppUser: () => ({ user: { username: 'alice', roles: ['automation_advanced'] } })
}));

vi.mock('api', () => ({
  default: {
    action: {
      patch: (id: string, body: any) => ({ op: 'patch', id, body }),
      operations: { get: () => ({ op: 'get-operations' }) },
      get: (id: string) => ({ op: 'get-action', id })
    }
  }
}));

vi.mock('components/app/providers/ModalProvider', () => ({
  ModalContext: modalContextToken
}));

vi.mock('components/elements/addons/layout/FlexOne', () => ({
  default: () => <div>flex</div>
}));

vi.mock('components/elements/addons/search/phrase/Phrase', () => ({
  default: ({ value, startAdornment }: any) => <div>{startAdornment}<div>{`phrase:${value}`}</div></div>
}));

vi.mock('components/elements/display/HowlerAvatar', () => ({
  default: ({ userId }: any) => <div>{`avatar:${userId}`}</div>
}));

vi.mock('components/elements/membership/MembershipManagement', () => ({
  MembershipManagement: () => <div>membership-management</div>
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('components/hooks/useMySnackbar', () => ({
  default: () => ({ showSuccessMessage: mockShowSuccessMessage })
}));

vi.mock('components/routes/action/shared/OperationEntry', () => ({
  default: ({ operation, values }: any) => <div>{`operation:${operation.id}:${values.kind}`}</div>
}));

vi.mock('plugins/store', () => ({
  default: { operations: ['plugin-op'] }
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context?.name === 'modal-context') {
        return { withConfirmDeleteModal: async (cb: any) => cb() };
      }
      return actual.useContext(context);
    }
  };
});

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-pluggable', () => ({
  usePluginStore: () => ({ executeFunction: mockPluginExecute })
}));

vi.mock('react-router', () => ({
  Link: ({ children, to }: any) => <a href={to}>{children}</a>,
  useParams: () => ({ id: 'action-1' })
}));

vi.mock('../../../elements/display/QueryResultText', () => ({
  default: ({ count, query }: any) => <div>{`query-result:${count}:${query}`}</div>
}));

vi.mock('../shared/ActionReportDisplay', () => ({
  default: ({ report }: any) => <div>{`report:${report.status}`}</div>
}));

vi.mock('../useMyActionFunctions', () => ({
  default: () => ({
    response: { total: 7 },
    onSearch: mockOnSearch,
    loading: true,
    setLoading: mockSetLoading,
    executeAction: mockExecuteAction,
    deleteAction: mockDeleteAction,
    progress: [2, 4],
    report: { status: 'done' }
  })
}));

import ActionDetails from './ActionDetails';

describe('ActionDetails', () => {
  beforeEach(() => {
    mockDispatchApi.mockReset();
    mockShowSuccessMessage.mockReset();
    mockExecuteAction.mockReset();
    mockDeleteAction.mockReset();
    mockOnSearch.mockReset();
    mockSetLoading.mockReset();
    mockPluginExecute.mockClear();

    mockDispatchApi.mockImplementation(async (request: any) => {
      if (request.op === 'get-operations') {
        return [
          { id: 'direct-op', triggers: ['manual', 'alert'] },
          { id: 'plugin-op', triggers: ['alert'] }
        ];
      }

      if (request.op === 'get-action') {
        return {
          action_id: 'action-1',
          owner: 'alice',
          name: 'My action',
          query: 'status:open',
          admins: ['alice'],
          members: ['alice'],
          triggers: ['manual'],
          operations: [
            { operation_id: 'direct-op', data_json: { kind: 'direct' } },
            { operation_id: 'plugin-op', data_json: { kind: 'plugin' } }
          ]
        };
      }

      return request;
    });
  });

  it('loads action details, searches, patches triggers, executes, deletes, and renders operations', async () => {
    render(<ActionDetails />);

    await waitFor(() => expect(mockDispatchApi).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(mockOnSearch).toHaveBeenCalledWith('status:open'));

    expect(screen.getByText('My action')).toBeInTheDocument();
    expect(screen.getByText('avatar:alice')).toBeInTheDocument();
    expect(screen.getByText('query-result:7:status:open')).toBeInTheDocument();
    expect(screen.getByText('report:done')).toBeInTheDocument();
    expect(screen.getByText('progress:50')).toBeInTheDocument();
    expect(screen.getByText('operation:direct-op:direct')).toBeInTheDocument();
    expect(screen.getByText('plugin-operation')).toBeInTheDocument();

    fireEvent.click(screen.getByText('search-icon').parentElement!);
    expect(mockOnSearch).toHaveBeenCalledWith('status:open');

    fireEvent.click(screen.getByLabelText('alert'));
    await waitFor(() =>
      expect(mockDispatchApi).toHaveBeenCalledWith({ op: 'patch', id: 'action-1', body: { triggers: ['manual', 'alert'] } })
    );

    fireEvent.click(screen.getByText('route.actions.execute'));
    expect(mockExecuteAction).toHaveBeenCalledWith('action-1');

    fireEvent.click(screen.getByText('button.delete'));
    await waitFor(() => expect(mockDeleteAction).toHaveBeenCalledWith('action-1'));
    expect(mockShowSuccessMessage).toHaveBeenCalledWith('route.actions.manager.delete.success');

    expect(screen.getByRole('link', { name: 'route.actions.edit' })).toHaveAttribute('href', '/action/action-1/edit');
  });
});
