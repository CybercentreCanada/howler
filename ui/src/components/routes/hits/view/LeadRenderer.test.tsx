/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('@mui/material', () => ({
  Box: ({ children }: any) => <div>{children}</div>,
  Divider: () => <hr />,
  Stack: ({ children }: any) => <div>{children}</div>,
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/elements/display/AiTriageMarkdown', () => ({
  default: ({ md }: any) => <div id="safe-ai-markdown">{md}</div>
}));

vi.mock('components/elements/display/HandlebarsMarkdown', () => ({
  default: ({ md }: any) => <div id="handlebars-markdown">{md}</div>
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-pluggable', () => ({
  usePluginStore: () => ({ executeFunction: vi.fn() })
}));

import LeadRenderer from './LeadRenderer';

describe('LeadRenderer', () => {
  it('uses inert markdown only for AI-owned leads and preserves normal leads', () => {
    const { rerender } = render(
      <LeadRenderer
        lead={
          {
            format: 'markdown',
            content: 'AI result',
            metadata: JSON.stringify({ owner: 'howler.ai_triage', schema_version: 1 })
          } as any
        }
      />
    );

    expect(screen.getByTestId('safe-ai-markdown')).toHaveTextContent('AI result');
    expect(screen.queryByTestId('handlebars-markdown')).not.toBeInTheDocument();

    rerender(<LeadRenderer lead={{ format: 'markdown', content: 'Template {{hit.id}}', metadata: '{}' } as any} />);
    expect(screen.getByTestId('handlebars-markdown')).toHaveTextContent('Template {{hit.id}}');
    expect(screen.queryByTestId('safe-ai-markdown')).not.toBeInTheDocument();
  });
});
