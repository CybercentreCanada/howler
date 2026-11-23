/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('@tui/core', () => ({
  PageCenter: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/elements/display/HandlebarsMarkdown', () => ({
  default: ({ md, object }: { md: string; object?: any }) => (
    <div>
      {md}
      <span>{object?.howler?.status}</span>
    </div>
  )
}));

vi.mock('components/hooks/useScrollRestoration', () => ({
  useScrollRestoration: vi.fn()
}));

vi.mock('../overviews/startingTemplate', () => ({
  useStartingTemplate: () => 'starting template'
}));

vi.mock('../ErrorBoundary', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

import OverviewDocumentation from './OverviewDocumentation';

describe('OverviewDocumentation', () => {
  it('renders the starting overview template inside the markdown renderer', () => {
    render(<OverviewDocumentation />);

    expect(screen.getByText('starting template')).toBeInTheDocument();
  });

  it('provides example hit data so the helper examples can render', () => {
    render(<OverviewDocumentation />);

    expect(screen.getByText('open')).toBeInTheDocument();
  });
});
