/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockShowSuccessMessage = vi.hoisted(() => vi.fn());
const mockCountPost = vi.hoisted(() => vi.fn());

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return {
    ...actual,
    Check: () => <div>check-icon</div>,
    Edit: () => <div>edit-icon</div>
  };
});

vi.mock('@mui/material', () => ({
  Alert: ({ children }: any) => <div>{children}</div>,
  AlertTitle: ({ children }: any) => <div>{children}</div>,
  Box: ({ children }: any) => <div>{children}</div>,
  Card: ({ children }: any) => <div>{children}</div>,
  CardContent: ({ children }: any) => <div>{children}</div>,
  CircularProgress: () => <div>loading-indicator</div>,
  Divider: () => <div>divider</div>,
  IconButton: ({ children, onClick }: any) => <button onClick={onClick}>{children}</button>,
  Skeleton: () => <div>loading</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  TextField: ({ value, onChange }: any) => <textarea aria-label="edit-description" value={value} onChange={onChange} />,
  Typography: ({ children }: any) => <div>{children}</div>,
  useMediaQuery: () => false,
  useTheme: () => ({ breakpoints: { down: () => 'md' }, spacing: (n: number) => `${n * 8}px` })
}));

vi.mock('api', () => ({
  default: {
    analytic: {
      put: (id: string, payload: any) => ({ id, payload, op: 'put' })
    },
    search: {
      count: {
        hit: {
          post: mockCountPost
        }
      }
    }
  }
}));

vi.mock('chartjs-adapter-dayjs-4', () => ({}));

vi.mock('components/elements/display/Markdown', () => ({
  default: ({ md }: any) => <div>{`markdown:${md}`}</div>
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('components/hooks/useMySnackbar', () => ({
  default: () => ({ showSuccessMessage: mockShowSuccessMessage })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('./widgets/Assessment', () => ({ default: () => <div>assessment</div> }));
vi.mock('./widgets/Created', () => ({ default: () => <div>created</div> }));
vi.mock('./widgets/Detection', () => ({ default: () => <div>detection</div> }));
vi.mock('./widgets/Escalation', () => ({ default: () => <div>escalation</div> }));
vi.mock('./widgets/Status', () => ({ default: () => <div>status</div> }));

import AnalyticOverview from './AnalyticOverview';

describe('AnalyticOverview', () => {
  beforeEach(() => {
    mockDispatchApi.mockReset();
    mockShowSuccessMessage.mockReset();
    mockCountPost.mockReset();
  });

  it('shows an empty-state warning when no hits match the analytic', async () => {
    mockCountPost.mockResolvedValueOnce({ count: 0 });

    render(<AnalyticOverview analytic={{ analytic_id: 'an-1', name: 'Alpha', description: 'desc' } as any} setAnalytic={vi.fn()} />);

    await waitFor(() => expect(mockCountPost).toHaveBeenCalledWith({ query: 'howler.analytic:"Alpha"' }));
    expect(screen.getByText('route.analytics.overview.empty.title')).toBeInTheDocument();
    expect(screen.getByText('route.analytics.overview.empty.description')).toBeInTheDocument();
  });

  it('renders statistics and saves edited markdown descriptions', async () => {
    const setAnalytic = vi.fn();
    mockCountPost.mockResolvedValueOnce({ count: 2 });
    mockDispatchApi.mockResolvedValueOnce({ analytic_id: 'an-1', description: 'updated' });

    render(<AnalyticOverview analytic={{ analytic_id: 'an-1', name: 'Alpha', description: 'original' } as any} setAnalytic={setAnalytic} />);

    await waitFor(() => expect(screen.getByText('created')).toBeInTheDocument());
    expect(screen.getByText('assessment')).toBeInTheDocument();
    expect(screen.getByText('status')).toBeInTheDocument();
    expect(screen.getByText('detection')).toBeInTheDocument();
    expect(screen.getByText('markdown:original')).toBeInTheDocument();

    fireEvent.click(screen.getByText('edit-icon'));
    fireEvent.change(screen.getByLabelText('edit-description'), { target: { value: 'updated' } });
    fireEvent.click(screen.getByText('check-icon'));

    await waitFor(() =>
      expect(mockDispatchApi).toHaveBeenCalledWith(
        { id: 'an-1', op: 'put', payload: { description: 'updated' } },
        { showError: true, throwError: true }
      )
    );
    expect(setAnalytic).toHaveBeenCalledWith({ analytic_id: 'an-1', description: 'updated' });
    expect(mockShowSuccessMessage).toHaveBeenCalledWith('route.analytics.updated');
  });
});
