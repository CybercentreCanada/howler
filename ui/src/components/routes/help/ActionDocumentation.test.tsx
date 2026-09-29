/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

const mockUseMediaQuery = vi.hoisted(() => vi.fn(() => false));
const mockSetSearchParams = vi.hoisted(() => vi.fn());
const searchParams = new URLSearchParams({ tab: 'plugin-doc' });
const mockExecuteFunction = vi.hoisted(() =>
  vi.fn(() => ({
    id: 'plugin-doc',
    i18nKey: 'plugin.doc',
    component: () => <div>plugin documentation</div>
  }))
);

vi.mock('@mui/material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/material')>();
  return {
    ...actual,
    useMediaQuery: mockUseMediaQuery
  };
});

vi.mock('@tui/core', () => ({
  PageCenter: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/hooks/useScrollRestoration', () => ({
  useScrollRestoration: vi.fn()
}));

vi.mock('plugins/store', () => ({
  default: {
    operations: ['triage']
  }
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-pluggable', () => ({
  usePluginStore: () => ({ executeFunction: mockExecuteFunction })
}));

vi.mock('react-router', () => ({
  useSearchParams: () => [searchParams, mockSetSearchParams]
}));

vi.mock('./ActionIntroductionDocumentation', () => ({
  default: () => <div>intro documentation</div>
}));

vi.mock('./components/HelpTabs', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

import ActionDocumentation from './ActionDocumentation';

describe('ActionDocumentation', () => {
  it('renders plugin documentation from the selected tab and updates search params on tab change', async () => {
    const user = userEvent.setup();

    render(<ActionDocumentation />);

    expect(screen.getByText('plugin documentation')).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'help.actions.introduction' }));

    expect(screen.getByText('intro documentation')).toBeInTheDocument();
    expect(mockSetSearchParams).toHaveBeenCalled();
    expect(mockExecuteFunction).toHaveBeenCalledWith('operation.triage.documentation');
  });
});
