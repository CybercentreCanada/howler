/// <reference types="vitest" />
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockFacetPost = vi.hoisted(() => vi.fn());
const mockHistogramPost = vi.hoisted(() => vi.fn());

vi.mock('@mui/material', () => ({
  Skeleton: () => <div>loading</div>
}));

vi.mock('api', () => ({
  default: {
    search: {
      facet: { hit: { post: mockFacetPost } },
      histogram: { hit: { post: mockHistogramPost } }
    }
  }
}));

vi.mock('chartjs-adapter-dayjs-4', () => ({}));

vi.mock('components/hooks/useMyChart', () => ({
  default: () => ({
    line: (title: string) => ({ plugins: { legend: { title } }, scales: { y: { beginAtZero: true } } })
  })
}));

vi.mock('react-chartjs-2', () => ({
  Line: ({ data, options }: any) => <div>{JSON.stringify({ data, options })}</div>
}));

import Stacked from './Stacked';

describe('Stacked', () => {
  beforeEach(() => {
    mockFacetPost.mockReset();
    mockHistogramPost.mockReset();
  });

  it('shows a skeleton without an analytic', () => {
    render(<Stacked analytic={undefined as any} field="howler.status" />);
    expect(screen.getByText('loading')).toBeInTheDocument();
  });

  it('loads facet and histogram data into stacked chart datasets', async () => {
    mockFacetPost.mockResolvedValueOnce({ 'howler.status': { open: 4, closed: 2 } });
    mockHistogramPost
      .mockResolvedValueOnce({ '2024-01-01T00:00:00Z': 2, '2024-01-02T00:00:00Z': 3 })
      .mockResolvedValueOnce({ '2024-01-01T00:00:00Z': 1, '2024-01-02T00:00:00Z': 1 });

    render(<Stacked analytic={{ name: 'Alpha' } as any} field="howler.status" color={value => `${value}-color`} />);

    await waitFor(() => expect(mockFacetPost).toHaveBeenCalledWith({ query: 'howler.analytic:("Alpha")', fields: ['howler.status'] }));
    await waitFor(() => expect(mockHistogramPost).toHaveBeenCalledTimes(2));

    const output = screen.getByText(/route.analytics.status.title/).textContent ?? '';
    expect(output).toContain('"stacked":true');
    expect(output).toContain('"label":"open"');
    expect(output).toContain('"label":"closed"');
    expect(output).toContain('"borderColor":"open-color"');
  });
});
