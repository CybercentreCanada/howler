/// <reference types="vitest" />
import { act, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockSetLoading = vi.hoisted(() => vi.fn());
const mockOnSearch = vi.hoisted(() => vi.fn(async () => {}));
const fieldContextToken = vi.hoisted(() => ({ name: 'field-context' }));
const mockGetHitFields = vi.hoisted(() => vi.fn());
const mockSearchParams = vi.hoisted(() => new URLSearchParams());
const mockSetSearchParams = vi.hoisted(() => vi.fn());

let paramsValue: { id?: string } = { id: 'action-a' };
let locationValue = { pathname: '/action/action-a/edit' };
const actionLoadResolvers: Record<string, Array<(value: any) => void>> = {};

vi.mock('@mui/icons-material', () => ({
  Add: () => null,
  PlayCircleOutline: () => null,
  Save: () => null
}));

vi.mock('@mui/material', () => {
  const wrapper = ({ children }: any) => <div>{children}</div>;
  return {
    Button: ({ children, disabled }: any) => <button disabled={disabled}>{children}</button>,
    Card: wrapper,
    CardContent: wrapper,
    Checkbox: () => <input type="checkbox" />,
    CircularProgress: () => <span>loading</span>,
    FormControlLabel: wrapper,
    FormGroup: wrapper,
    IconButton: ({ children }: any) => <button>{children}</button>,
    Stack: wrapper,
    TextField: ({ label, value }: any) => <input aria-label={label} value={value} readOnly />,
    Tooltip: wrapper,
    Typography: wrapper
  };
});

vi.mock('@tui/core', () => ({
  PageCenter: ({ children }: any) => <div>{children}</div>,
  useAppUser: () => ({ user: { username: 'alice', roles: [] } })
}));

vi.mock('api', () => ({
  default: {
    action: { operations: { get: () => ({ kind: 'operations' }) } },
    search: {
      action: {
        post: ({ query }: { query: string }) => ({
          kind: 'action-search',
          actionId: query.replace('action_id:', '')
        })
      },
      hit: { post: (query: any) => query }
    }
  }
}));

vi.mock('components/app/providers/FieldProvider', () => ({
  FieldContext: fieldContextToken
}));
vi.mock('components/elements/display/icons/SocketBadge', () => ({ default: () => null }));
vi.mock('components/routes/hits/search/RecordQuery', () => ({ default: () => null }));
vi.mock('../../../elements/display/QueryResultText', () => ({ default: () => null }));
vi.mock('../shared/ActionReportDisplay', () => ({ default: () => null }));
vi.mock('../shared/OperationEntry', () => ({ default: () => null }));
vi.mock('../useMyActionFunctions', () => ({
  default: () => ({
    contextReady: true,
    response: undefined,
    loading: false,
    setLoading: mockSetLoading,
    responseQuery: '',
    report: undefined,
    onSearch: mockOnSearch,
    saveAction: vi.fn(),
    submitAction: vi.fn()
  })
}));
vi.mock('plugins/store', () => ({ default: { operations: [] } }));
vi.mock('react-pluggable', () => ({ usePluginStore: () => ({ executeFunction: vi.fn() }) }));
vi.mock('react-router', () => ({
  useLocation: () => locationValue,
  useParams: () => paramsValue,
  useSearchParams: () => [mockSearchParams, mockSetSearchParams]
}));
vi.mock('components/hooks/useMyApi', () => ({ default: () => ({ dispatchApi: mockDispatchApi }) }));
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) =>
      context === fieldContextToken ? { getHitFields: mockGetHitFields } : actual.useContext(context)
  };
});

import ActionEditor from './ActionEditor';

describe('ActionEditor route visits', () => {
  beforeEach(() => {
    paramsValue = { id: 'action-a' };
    locationValue = { pathname: '/action/action-a/edit' };
    mockDispatchApi.mockReset();
    mockSetLoading.mockClear();
    mockOnSearch.mockClear();
    mockSearchParams.delete('query');
    mockSetSearchParams.mockClear();
    for (const actionId of Object.keys(actionLoadResolvers)) {
      delete actionLoadResolvers[actionId];
    }
    mockDispatchApi.mockImplementation((request: any) => {
      if (request.kind === 'operations') {
        return Promise.resolve([]);
      }
      return new Promise(resolve => {
        const resolvers = actionLoadResolvers[request.actionId] ?? [];
        resolvers.push(resolve);
        actionLoadResolvers[request.actionId] = resolvers;
      });
    });
  });

  it('does not apply an old action load after leaving and revisiting the same ID', async () => {
    const { rerender } = render(<ActionEditor />);
    await waitFor(() => expect(actionLoadResolvers['action-a']).toHaveLength(1));

    paramsValue = { id: 'action-b' };
    locationValue = { pathname: '/action/action-b/edit' };
    rerender(<ActionEditor />);
    await waitFor(() => expect(actionLoadResolvers['action-b']).toHaveLength(1));

    paramsValue = { id: 'action-a' };
    locationValue = { pathname: '/action/action-a/edit' };
    rerender(<ActionEditor />);
    await waitFor(() => expect(actionLoadResolvers['action-a']).toHaveLength(2));

    await act(async () => {
      actionLoadResolvers['action-a'][1]!({
        items: [{ name: 'Current A', query: 'status:current', operations: [] }]
      });
    });
    await waitFor(() => expect(screen.getByLabelText('route.actions.name')).toHaveValue('Current A'));

    const loadingCallsAfterCurrentLoad = mockSetLoading.mock.calls.length;
    await act(async () => {
      actionLoadResolvers['action-a'][0]!({ items: [{ name: 'Stale A', query: 'status:stale', operations: [] }] });
    });

    expect(screen.getByLabelText('route.actions.name')).toHaveValue('Current A');
    expect(mockOnSearch).toHaveBeenCalledTimes(1);
    expect(mockOnSearch).toHaveBeenCalledWith('status:current');
    expect(mockSetLoading).toHaveBeenCalledTimes(loadingCallsAfterCurrentLoad);
  });
});
