/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const mockModifyDocumentation = vi.hoisted(() => vi.fn((md: string) => `modified:${md.slice(0, 10)}`));

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
  useTranslation: () => ({ i18n: { language: 'en' } })
}));

vi.mock('react-pluggable', () => ({
  usePluginStore: () => ({})
}));

vi.mock('utils/utils', () => ({
  modifyDocumentation: mockModifyDocumentation
}));

import AuthDocumentation from './AuthDocumentation';

describe('AuthDocumentation', () => {
  it('renders transformed authentication markdown', () => {
    render(<AuthDocumentation />);

    expect(screen.getByText(/^modified:/)).toBeInTheDocument();
    expect(mockModifyDocumentation).toHaveBeenCalled();
  });
});
