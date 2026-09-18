/// <reference types="vitest" />
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockFacetPost = vi.hoisted(() => vi.fn());

vi.mock('@mui/material', () => ({
  Box: ({ children }: any) => <div>{children}</div>,
  Skeleton: () => <div>loading</div>,
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('api', () => ({
  default: {
    search: {
      facet: { hit: { post: mockFacetPost } }
    }
  }
}));

vi.mock('chartjs-adapter-dayjs-4', () => ({}));

vi.mock('components/hooks/useMyChart', () => ({
  default: () => ({
    bar: (title: string) => ({ title })
  })
}));

vi.mock('react-chartjs-2', () => ({
  Bar: ({ data, options }: any) => <div>{JSON.stringify({ data, options })}</div>
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

import Assessment from './Assessment';

describe('Assessment', () => {
  beforeEach(() => {
    mockFacetPost.mockReset();
  });

  it('shows a skeleton when no analytic is provided', () => {
    render(<Assessment analytic={undefined as any} />);
    expect(screen.getByText('loading')).toBeInTheDocument();
  });

  it('renders a bar chart with facet data', async () => {
    mockFacetPost.mockResolvedValueOnce({ 'howler.assessment': { malicious: 3, suspicious: 1 } });
    render(<Assessment analytic={{ name: 'Alpha' } as any} />);
    await waitFor(() => expect(screen.getByText(/route.analytics.assessment.title/)).toBeInTheDocument());
    expect(screen.getByText(/"malicious"/)).toBeInTheDocument();
  });
});
