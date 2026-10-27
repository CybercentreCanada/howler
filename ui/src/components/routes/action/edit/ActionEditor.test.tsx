/// <reference types="vitest" />
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockHistoryProps = vi.hoisted(() => vi.fn());
const mockHookState = vi.hoisted(() => ({ acceptedRunIds: ['run-ad-hoc'] as string[] }));
const fieldContextToken = vi.hoisted(() => ({ name: 'field-context' }));
const mockSearchParams = vi.hoisted(() => new URLSearchParams());
const mockSetSearchParams = vi.hoisted(() => vi.fn());

vi.mock('@mui/icons-material', () => ({
  Add: () => <span>add</span>,
  PlayCircleOutline: () => <span>play</span>,
  Save: () => <span>save</span>,
  PsychologyAlt: () => null,
  LocalPolice: () => null,
  MoodBad: () => null,
  NewReleases: () => null,
  Star: () => null,
  Timeline: () => null
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
    LinearProgress: () => <div>progress</div>,
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
    search: { hit: { post: (query: any) => query } }
  }
}));

vi.mock('components/app/providers/FieldProvider', () => ({
  FieldContext: fieldContextToken
}));

vi.mock('components/elements/display/icons/SocketBadge', () => ({
  default: () => <span>socket-badge</span>
}));

vi.mock('components/routes/hits/search/RecordQuery', () => ({
  default: () => <div>record-query</div>
}));

vi.mock('components/elements/display/QueryResultText', () => ({
  default: () => <div>query-result</div>
}));

vi.mock('../shared/ActionReportDisplay', () => ({
  default: () => <div>action-report</div>
}));

vi.mock('../shared/ActionRunHistory', () => ({
  default: (props: any) => {
    mockHistoryProps(props);
    return <div>run-history</div>;
  }
}));

vi.mock('../shared/OperationEntry', () => ({
  default: () => <div>operation-entry</div>
}));

vi.mock('../useMyActionFunctions', () => ({
  default: () => ({
    response: undefined,
    loading: false,
    setLoading: vi.fn(),
    responseQuery: '',
    report: {
      ai_triage: [
        {
          query: '*',
          outcome: 'success',
          title: 'Accepted',
          message: 'Queued',
          status: 'queued',
          run_id: 'run-ad-hoc'
        }
      ]
    },
    acceptedRunIds: mockHookState.acceptedRunIds,
    progress: [0, 0],
    onSearch: vi.fn(),
    saveAction: vi.fn(),
    submitAction: vi.fn()
  })
}));

vi.mock('plugins/store', () => ({
  default: { operations: [] }
}));

vi.mock('react-pluggable', () => ({
  usePluginStore: () => ({ executeFunction: vi.fn() })
}));

vi.mock('react-router', () => ({
  useLocation: () => ({ pathname: '/action/new' }),
  useParams: () => ({}),
  useSearchParams: () => [mockSearchParams, mockSetSearchParams]
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) =>
      context === fieldContextToken ? { getHitFields: vi.fn() } : actual.useContext(context)
  };
});

import ActionEditor from './ActionEditor';

describe('ActionEditor', () => {
  beforeEach(() => {
    mockDispatchApi.mockReset();
    mockDispatchApi.mockResolvedValue([]);
    mockHistoryProps.mockClear();
    mockHookState.acceptedRunIds = ['run-ad-hoc'];
    mockSearchParams.delete('query');
    mockSetSearchParams.mockClear();
  });

  it('tracks accepted ad hoc runs even when the server hides the operation', async () => {
    render(<ActionEditor />);

    await waitFor(() => expect(mockHistoryProps).toHaveBeenCalled());
    expect(mockHistoryProps).toHaveBeenLastCalledWith(
      expect.objectContaining({
        actionId: undefined,
        contextId: '/action/new',
        acceptedRunIds: ['run-ad-hoc']
      })
    );
    expect(screen.getByText('run-history')).toBeInTheDocument();
  });

  it('omits history for an unrelated new action', async () => {
    mockHookState.acceptedRunIds = [];
    render(<ActionEditor />);

    await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
    expect(screen.queryByText('run-history')).not.toBeInTheDocument();
    expect(mockHistoryProps).not.toHaveBeenCalled();
  });
});
