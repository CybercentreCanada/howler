/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const mockModifyDocumentation = vi.hoisted(() => vi.fn((md: string) => `client:${md.slice(0, 10)}`));

vi.mock('@tui/core', () => ({
  PageCenter: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/elements/display/Markdown', () => ({
  default: ({ md }: { md: string }) => <div>{md}</div>
}));

vi.mock('components/hooks/useScrollRestoration', () => ({
  useScrollRestoration: vi.fn()
}));

vi.mock('plugins/store', () => ({
  default: { plugins: [] }
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ i18n: { language: 'fr' } })
}));

vi.mock('react-pluggable', () => ({
  usePluginStore: () => ({})
}));

vi.mock('utils/utils', () => ({
  modifyDocumentation: mockModifyDocumentation
}));

import ClientDocumentation from './ClientDocumentation';

describe('ClientDocumentation', () => {
  it('renders transformed client markdown', () => {
    render(<ClientDocumentation />);

    expect(screen.getByText(/^client:/)).toBeInTheDocument();
    expect(mockModifyDocumentation).toHaveBeenCalled();
  });
});
