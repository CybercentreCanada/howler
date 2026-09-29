/// <reference types="vitest" />
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockGetOverviews = vi.hoisted(() => vi.fn(async () => undefined));
const overviewContextToken = vi.hoisted(() => ({ name: 'overview-context' }));

let overviewsValue: any[] = [];

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return { ...actual, Article: () => <div>article-icon</div> };
});

vi.mock('@mui/material', () => ({
  Box: ({ children }: any) => <div>{children}</div>,
  Fab: ({ children }: any) => <div>{children}</div>,
  Skeleton: () => <div>loading</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  Typography: ({ children }: any) => <div>{children}</div>,
  useMediaQuery: () => false
}));

vi.mock('@tui/core', () => ({
  AppListEmpty: () => <div>empty</div>
}));

vi.mock('chartjs-adapter-dayjs-4', () => ({}));

vi.mock('components/app/providers/OverviewProvider', () => ({
  OverviewContext: overviewContextToken
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-router', () => ({
  Link: ({ children }: any) => <div>{children}</div>
}));

vi.mock('../overviews/OverviewCard', () => ({
  default: ({ overview }: any) => <div>{`overview:${overview.overview_id}:${overview.detection ?? ''}`}</div>
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === overviewContextToken) {
        return { getOverviews: mockGetOverviews, overviews: overviewsValue };
      }
      return actual.useContext(context);
    }
  };
});

import AnalyticOverviews from './AnalyticOverviews';

describe('AnalyticOverviews', () => {
  beforeEach(() => {
    overviewsValue = [];
    mockGetOverviews.mockClear();
  });

  it('shows a skeleton when the analytic is missing', () => {
    render(<AnalyticOverviews analytic={undefined as any} />);
    expect(screen.getByText('loading')).toBeInTheDocument();
  });

  it('loads matching overviews and falls back to the empty state', async () => {
    overviewsValue = [
      { overview_id: 'o1', analytic: 'Alpha', detection: 'Det1' },
      { overview_id: 'o2', analytic: 'Beta' }
    ];

    const { rerender } = render(<AnalyticOverviews analytic={{ name: 'Alpha' } as any} />);

    await waitFor(() => expect(mockGetOverviews).toHaveBeenCalled());
    expect(screen.getByText('overview:o1:Det1')).toBeInTheDocument();
    expect(screen.getByText('route.overviews.create')).toBeInTheDocument();

    rerender(<AnalyticOverviews analytic={{ name: 'Gamma' } as any} />);
    await waitFor(() => expect(screen.getByText('empty')).toBeInTheDocument());
  });
});
