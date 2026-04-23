import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { Case } from 'models/entities/generated/Case';
import type { Rule } from 'models/entities/generated/Rule';
import { createMockCase } from 'tests/utils';
import { describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockUpdate = vi.hoisted(() => vi.fn());
const mockShowModal = vi.hoisted(() => vi.fn());
const mockCase = vi.hoisted(() => ({
  current: {
    case_id: 'case-001',
    title: 'Test Case',
    rules: []
  } as Case
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('components/app/providers/ModalProvider', async () => {
  const { createContext } = await import('react');
  return {
    ModalContext: createContext({ showModal: mockShowModal, close: vi.fn(), setContent: vi.fn() })
  };
});

vi.mock('../hooks/useCase', () => ({
  default: ({ case: c }: { case?: Case }) => ({
    case: c ?? mockCase.current,
    update: mockUpdate,
    loading: false,
    missing: false
  })
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useOutletContext: () => mockCase.current,
    useLocation: () => ({ pathname: '/cases/case-001/rules', search: '' }),
    useParams: () => ({ id: 'case-001' }),
    useNavigate: () => vi.fn()
  };
});

const mockOnSubmit = vi.hoisted(() => ({ current: null as ((data: any) => Promise<void>) | null }));

vi.mock('./CreateRuleDialog', () => ({
  default: ({
    open,
    onClose,
    onSubmit
  }: {
    open: boolean;
    onClose: () => void;
    onSubmit: (data: any) => Promise<void>;
  }) => {
    mockOnSubmit.current = onSubmit;
    return open ? (
      <div id="create-rule-dialog">
        <button
          id="rule-submit-button"
          onClick={() => onSubmit({ query: 'event.kind:alert', destination: 'alerts/incoming' })}
        >
          submit
        </button>
        <button onClick={onClose}>cancel</button>
      </div>
    ) : null;
  }
}));

vi.mock('api', () => ({
  default: {
    v2: {
      case: {
        rules: {
          post: vi.fn(),
          del: vi.fn(),
          put: vi.fn()
        }
      }
    }
  }
}));

import api from 'api';
import CaseRules from './CaseRules';

const makeRule = (overrides?: Partial<Rule>): Rule => ({
  rule_id: 'rule-001',
  query: 'event.kind:alert',
  destination: 'alerts/{{howler.analytic}}',
  author: 'analyst1',
  enabled: true,
  timeframe: '2026-06-01T00:00:00.000Z',
  ...overrides
});

describe('CaseRules', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCase.current = createMockCase({
      case_id: 'case-001',
      title: 'Test Case',
      rules: []
    }) as Case;
  });

  it('renders empty state when no rules exist', () => {
    render(<CaseRules />);

    expect(screen.getByText('page.cases.rules.empty')).toBeInTheDocument();
  });

  it('renders rule list with destination, query, author, and timeframe', () => {
    mockCase.current = createMockCase({
      case_id: 'case-001',
      rules: [makeRule()]
    }) as Case;

    render(<CaseRules />);

    expect(screen.getByTestId('rules-table')).toBeInTheDocument();
    expect(screen.getByText('alerts/{{howler.analytic}}')).toBeInTheDocument();
    expect(screen.getByText('event.kind:alert')).toBeInTheDocument();
    expect(screen.getByText('analyst1')).toBeInTheDocument();
  });

  it('shows no expiry chip when timeframe is null', () => {
    mockCase.current = createMockCase({
      case_id: 'case-001',
      rules: [makeRule({ timeframe: undefined })]
    }) as Case;

    render(<CaseRules />);

    expect(screen.getByText('page.cases.rules.no_expiry')).toBeInTheDocument();
  });

  it('renders enabled toggle for each rule', () => {
    mockCase.current = createMockCase({
      case_id: 'case-001',
      rules: [makeRule()]
    }) as Case;

    render(<CaseRules />);

    const toggle = screen.getByTestId('rule-toggle-rule-001');
    expect(toggle).toBeInTheDocument();
  });

  it('opens create rule dialog when create button is clicked', async () => {
    const user = userEvent.setup();

    render(<CaseRules />);

    await act(async () => {
      await user.click(screen.getByTestId('create-rule-button'));
    });

    await waitFor(() => {
      expect(screen.getByTestId('create-rule-dialog')).toBeInTheDocument();
    });
  });

  it('submits create rule form and calls API', async () => {
    const user = userEvent.setup();

    const updatedCase = createMockCase({
      case_id: 'case-001',
      rules: [makeRule({ rule_id: 'new-rule' })]
    }) as Case;
    mockDispatchApi.mockResolvedValueOnce(updatedCase);
    (api.v2.case.rules.post as ReturnType<typeof vi.fn>).mockReturnValue('post-request');

    render(<CaseRules />);

    await act(async () => {
      await user.click(screen.getByTestId('create-rule-button'));
    });

    await waitFor(() => {
      expect(screen.getByTestId('create-rule-dialog')).toBeInTheDocument();
    });

    await act(async () => {
      await user.click(screen.getByTestId('rule-submit-button'));
    });

    await waitFor(() => {
      expect(mockDispatchApi).toHaveBeenCalledWith('post-request');
    });
  });

  it('calls delete API when delete is confirmed via modal', async () => {
    const user = userEvent.setup();

    mockCase.current = createMockCase({
      case_id: 'case-001',
      rules: [makeRule()]
    }) as Case;

    const updatedCase = createMockCase({ case_id: 'case-001', rules: [] }) as Case;
    mockDispatchApi.mockResolvedValueOnce(updatedCase);
    (api.v2.case.rules.del as ReturnType<typeof vi.fn>).mockReturnValue('del-request');

    // Make showModal immediately invoke the onConfirm callback
    mockShowModal.mockImplementation((modal: any) => {
      modal.props.onConfirm();
    });

    render(<CaseRules />);

    await act(async () => {
      await user.click(screen.getByTestId('rule-delete-rule-001'));
    });

    await waitFor(() => {
      expect(mockShowModal).toHaveBeenCalled();
      expect(mockDispatchApi).toHaveBeenCalledWith('del-request');
    });
  });

  it('calls put API when enabled toggle is clicked', async () => {
    const user = userEvent.setup();

    mockCase.current = createMockCase({
      case_id: 'case-001',
      rules: [makeRule({ enabled: true })]
    }) as Case;

    const updatedCase = createMockCase({
      case_id: 'case-001',
      rules: [makeRule({ enabled: false })]
    }) as Case;
    mockDispatchApi.mockResolvedValueOnce(updatedCase);
    vi.mocked(api.v2.case.rules.put).mockReturnValue('put-request' as any);

    render(<CaseRules />);

    const toggle = screen.getByTestId('rule-toggle-rule-001');

    await act(async () => {
      await user.click(toggle);
    });

    await waitFor(() => {
      expect(mockDispatchApi).toHaveBeenCalledWith('put-request');
    });
  });

  it('renders multiple rules', () => {
    mockCase.current = createMockCase({
      case_id: 'case-001',
      rules: [
        makeRule({ rule_id: 'rule-001', query: 'query1' }),
        makeRule({ rule_id: 'rule-002', query: 'query2', author: 'analyst2' })
      ]
    }) as Case;

    render(<CaseRules />);

    expect(screen.getByText('query1')).toBeInTheDocument();
    expect(screen.getByText('query2')).toBeInTheDocument();
    expect(screen.getByText('analyst2')).toBeInTheDocument();
  });
});
