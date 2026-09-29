/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const mockModifyDocumentation = vi.hoisted(() => vi.fn((md: string) => `view:${md.slice(0, 10)}`));

vi.mock('@tui/core', () => ({
  PageCenter: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/elements/display/Markdown', () => ({
  default: ({ md, components }: { md: string; components?: Record<string, React.ReactNode> }) => (
    <div>
      <div>{md}</div>
      {components?.search}
    </div>
  )
}));

vi.mock('components/hooks/useScrollRestoration', () => ({
  useScrollRestoration: vi.fn()
}));

vi.mock('plugins/store', () => ({
  default: { plugins: [] }
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ i18n: { language: 'en' } })
}));

vi.mock('react-pluggable', () => ({
  usePluginStore: () => ({})
}));

vi.mock('utils/utils', () => ({
  modifyDocumentation: mockModifyDocumentation
}));

import ViewDocumentation from './ViewDocumentation';

describe('ViewDocumentation', () => {
  it('renders transformed views markdown with the search icon component', () => {
    render(<ViewDocumentation />);

    expect(screen.getByText(/^view:/)).toBeInTheDocument();
    expect(document.querySelector('svg')).not.toBeNull();
  });
});
