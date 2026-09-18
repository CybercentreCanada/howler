/// <reference types="vitest" />
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return {
    ...actual,
    CheckCircleOutline: () => <div>complete-icon</div>,
    HourglassBottom: () => <div>range-icon</div>,
    RadioButtonUnchecked: () => <div>task-icon</div>,
    UpdateOutlined: () => <div>updated-icon</div>
  };
});

vi.mock('@mui/material', () => ({
  Chip: ({ label }: any) => <div>{label}</div>,
  Divider: () => <div>divider</div>,
  Grid: ({ children }: any) => <div>{children}</div>,
  Skeleton: () => <div>loading</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  Tooltip: ({ children }: any) => <div>{children}</div>,
  Typography: ({ children }: any) => <div>{children}</div>,
  useTheme: () => ({ palette: { success: { main: 'green' } }, spacing: (n: number) => `${n * 8}px` })
}));

vi.mock('api', () => ({
  default: {
    v2: {
      case: {
        get: (id: string) => ({ id })
      }
    }
  }
}));

vi.mock('components/elements/case/StatusIcon', () => ({
  default: ({ status }: any) => <div>{`status:${status}`}</div>
}));

vi.mock('components/elements/display/HowlerAvatar', () => ({
  default: ({ userId }: any) => <div>{`avatar:${userId}`}</div>
}));

vi.mock('components/elements/PluginChip', () => ({
  default: ({ label }: any) => <div>{`plugin:${label}`}</div>
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('dayjs', () => ({
  default: (value: string) => ({ toString: () => `date:${value}` })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('utils/utils', () => ({
  twitterShort: (value: string) => `short:${value}`
}));

vi.mock('../display/HowlerCard', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

import CaseCard from './CaseCard';

describe('CaseCard', () => {
  beforeEach(() => {
    mockDispatchApi.mockReset();
  });

  it('shows a skeleton while no case data is available', () => {
    render(<CaseCard />);
    expect(screen.getByText('loading')).toBeInTheDocument();
  });

  it('renders provided case details and loads by case id when needed', async () => {
    mockDispatchApi.mockResolvedValueOnce({
      case_id: 'case-2',
      title: 'Loaded case',
      status: 'resolved',
      updated: '2024-01-02T00:00:00Z',
      summary: 'Loaded summary',
      participants: ['alice'],
      targets: ['target-1'],
      indicators: ['indicator-1'],
      threats: ['threat-1'],
      tasks: [{ id: 't1', summary: 'done task', complete: true }, { id: 't2', summary: 'todo task', complete: false }]
    });

    const { rerender } = render(
      <CaseCard
        case={{
          case_id: 'case-1',
          title: 'Case title',
          status: 'resolved',
          updated: '2024-01-01T00:00:00Z',
          start: '2024-01-01',
          end: '2024-01-02',
          summary: 'First line\nSecond line',
          participants: ['alice', 'bob'],
          targets: ['target-1'],
          indicators: ['indicator-1'],
          threats: ['threat-1'],
          tasks: [{ id: 't1', summary: 'done task', complete: true }, { id: 't2', summary: 'todo task', complete: false }]
        } as any}
      />
    );

    expect(screen.getByText('Case title')).toBeInTheDocument();
    expect(screen.getByText('status:resolved')).toBeInTheDocument();
    expect(screen.getByText('short:2024-01-01 - short:2024-01-02')).toBeInTheDocument();
    expect(screen.getByText('short:2024-01-01T00:00:00Z')).toBeInTheDocument();
    expect(screen.getByText('First line')).toBeInTheDocument();
    expect(screen.getByText('avatar:alice')).toBeInTheDocument();
    expect(screen.getByText('plugin:target-1')).toBeInTheDocument();
    expect(screen.getByText('plugin:indicator-1')).toBeInTheDocument();
    expect(screen.getByText('plugin:threat-1')).toBeInTheDocument();
    expect(screen.getByText('1 complete')).toBeInTheDocument();
    expect(screen.getByText('todo task')).toBeInTheDocument();

    rerender(<CaseCard caseId="case-2" />);
    await waitFor(() => expect(mockDispatchApi).toHaveBeenCalledWith({ id: 'case-2' }, { throwError: false }));
    await waitFor(() => expect(screen.getByText('Loaded case')).toBeInTheDocument());
  });
});
