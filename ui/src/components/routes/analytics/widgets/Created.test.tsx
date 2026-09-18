/// <reference types="vitest" />
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHistogramPost = vi.hoisted(() => vi.fn());

vi.mock('@mui/material', () => ({
  Skeleton: () => <div>loading</div>
}));

vi.mock('api', () => ({
  default: {
    search: {
      histogram: { hit: { post: mockHistogramPost } }
    }
  }
}));

vi.mock('chartjs-adapter-dayjs-4', () => ({}));

vi.mock('components/hooks/useMyChart', () => ({
  default: () => ({
    line: (title: string) => ({ title })
  })
}));

vi.mock('react-chartjs-2', () => ({
  Line: ({ data, options }: any) => <div>{JSON.stringify({ data, options })}</div>
}));

import Created from './Created';

describe('Created', () => {
  beforeEach(() => {
    mockHistogramPost.mockReset();
  });

  it('renders a skeleton while no analytic is provided', () => {
    render(<Created analytic={undefined as any} />);
    expect(screen.getByText('loading')).toBeInTheDocument();
  });

  it('loads histogram data into the line chart', async () => {
    mockHistogramPost.mockResolvedValueOnce({ '2024-01-01T00:00:00Z': 2, '2024-01-02T00:00:00Z': 0 });
    render(<Created analytic={{ name: 'Alpha' } as any} />);
    await waitFor(() => expect(mockHistogramPost).toHaveBeenCalled());
    expect(screen.getByText(/route.analytics.ingestion.title/)).toBeInTheDocument();
    expect(screen.getByText(/"label":"Alpha"/)).toBeInTheDocument();
  });
});
