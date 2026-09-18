/// <reference types="vitest" />
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());

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

vi.mock('api', () => ({
  default: {
    template: {
      get: () => ({})
    }
  }
}));

vi.mock('chartjs-adapter-dayjs-4', () => ({}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-router', () => ({
  Link: ({ children }: any) => <div>{children}</div>
}));

vi.mock('../templates/TemplateCard', () => ({
  default: ({ template }: any) => <div>{`template:${template.template_id}:${template.detection ?? ''}:${template.type}`}</div>
}));

import AnalyticTemplates from './AnalyticTemplates';

describe('AnalyticTemplates', () => {
  beforeEach(() => {
    mockDispatchApi.mockReset();
  });

  it('shows a skeleton when the analytic is missing', () => {
    mockDispatchApi.mockResolvedValue([]);
    render(<AnalyticTemplates analytic={undefined as any} />);
    expect(screen.getByText('loading')).toBeInTheDocument();
  });

  it('loads matching templates and shows empty state when none match', async () => {
    mockDispatchApi.mockResolvedValueOnce([
      { template_id: 't1', analytic: 'Alpha', detection: 'Det1', type: 'global' },
      { template_id: 't2', analytic: 'Beta', type: 'personal' }
    ]);

    const { rerender } = render(<AnalyticTemplates analytic={{ name: 'Alpha' } as any} />);

    await waitFor(() => expect(screen.getByText('template:t1:Det1:global')).toBeInTheDocument());
    expect(screen.getByText('route.templates.create')).toBeInTheDocument();

    mockDispatchApi.mockResolvedValueOnce([{ template_id: 't2', analytic: 'Beta', type: 'personal' }]);
    rerender(<AnalyticTemplates analytic={{ name: 'Gamma' } as any} />);
    await waitFor(() => expect(screen.getByText('empty')).toBeInTheDocument());
  });
});
