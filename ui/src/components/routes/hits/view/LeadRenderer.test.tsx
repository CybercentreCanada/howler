/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('components/elements/display/Markdown', () => ({
  default: ({ untrusted }: any) => <div id="markdown">{String(!!untrusted)}</div>
}));

vi.mock('components/elements/display/HandlebarsMarkdown', () => ({
  default: ({ object }: any) => <div id="handlebars">{JSON.stringify(object)}</div>
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-pluggable', () => ({
  usePluginStore: () => ({ executeFunction: vi.fn() })
}));

import LeadRenderer from './LeadRenderer';

const renderLead = (metadata?: string) =>
  render(
    <LeadRenderer
      lead={{ format: 'markdown', content: 'body', metadata } as any}
      hit={{ user: { email: 'a@b.c' } } as any}
    />
  );

describe('LeadRenderer', () => {
  it('renders AI triage leads as untrusted markdown, never as a template with hit context', () => {
    renderLead(JSON.stringify({ owner: 'howler.ai_triage' }));

    expect(screen.getByTestId('markdown')).toHaveTextContent('true');
    expect(screen.queryByTestId('handlebars')).toBeNull();
  });

  it.each([undefined, '{}', JSON.stringify({ owner: 'another.plugin' }), 'not-json'])(
    'keeps other leads (metadata: %s) as templates evaluated against the hit',
    metadata => {
      renderLead(metadata);

      expect(screen.getByTestId('handlebars')).toHaveTextContent('a@b.c');
      expect(screen.queryByTestId('markdown')).toBeNull();
    }
  );
});
