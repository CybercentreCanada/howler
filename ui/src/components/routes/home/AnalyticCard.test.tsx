/// <reference types="vitest" />
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockGetAnalyticFromId = vi.hoisted(() => vi.fn());
const resetZoom = vi.fn();
const analyticContextToken = vi.hoisted(() => ({ name: 'analytic-context' }));

vi.mock('@mui/icons-material', () => ({
  CenterFocusWeak: () => <div>reset-icon</div>,
  OpenInNew: () => <div>open-icon</div>
}));

vi.mock('@mui/material', () => ({
  Box: ({ children }: any) => <div>{children}</div>,
  Card: ({ children }: any) => <div>{children}</div>,
  CardContent: ({ children }: any) => <div>{children}</div>,
  IconButton: ({ children, onClick }: any) => <button onClick={onClick}>{children}</button>,
  Skeleton: () => <div>loading</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  Tooltip: ({ children }: any) => <div>{children}</div>,
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/app/providers/AnalyticProvider', () => ({
  AnalyticContext: analyticContextToken
}));

vi.mock('components/elements/addons/layout/FlexOne', () => ({
  default: () => <div>flex</div>
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === analyticContextToken) return { getAnalyticFromId: mockGetAnalyticFromId };
      return actual.useContext(context);
    }
  };
});

vi.mock('react-router', () => ({
  Link: ({ children, to }: any) => <a href={to}>{children}</a>
}));

vi.mock('../analytics/widgets/Assessment', () => ({
  default: () => <div>assessment-widget</div>
}));
vi.mock('../analytics/widgets/Created', () => ({
  default: (_props: any) => {
    if (_props.ref) _props.ref.current = { resetZoom };
    return <div>created-widget</div>;
  }
}));
vi.mock('../analytics/widgets/Detection', () => ({
  default: () => <div>detection-widget</div>
}));
vi.mock('../analytics/widgets/Escalation', () => ({
  default: () => <div>escalation-widget</div>
}));
vi.mock('../analytics/widgets/Status', () => ({
  default: () => <div>status-widget</div>
}));

import AnalyticCard from './AnalyticCard';

describe('AnalyticCard', () => {
  beforeEach(() => {
    mockGetAnalyticFromId.mockReset();
    resetZoom.mockReset();
  });

  it('loads analytic details and renders created charts with reset control', async () => {
    mockGetAnalyticFromId.mockResolvedValue({ analytic_id: 'a1', name: 'Analytic One' });
    render(<AnalyticCard analyticId="a1" type="created" />);

    expect(screen.getByText('loading')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('Analytic One')).toBeInTheDocument());
    expect(screen.getByText('created-widget')).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button')[1]);
    expect(resetZoom).toHaveBeenCalled();
  });

  it('renders the assessment and escalation widget variants', async () => {
    mockGetAnalyticFromId.mockResolvedValue({ analytic_id: 'a2', name: 'Analytic Two' });
    const { rerender } = render(<AnalyticCard analyticId="a2" type="assessment" />);

    await waitFor(() => expect(screen.getByText('assessment-widget')).toBeInTheDocument());
    rerender(<AnalyticCard analyticId="a2" type="escalation" />);
    await act(async () => {});
    expect(screen.getByText('escalation-widget')).toBeInTheDocument();
  });
});
