/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const mockModifyDocumentation = vi.hoisted(() => vi.fn((section: string) => `modified:${section}`));

vi.mock('@mui/material', () => ({
  Card: ({ children }: any) => <div>{children}</div>,
  CardContent: ({ children }: any) => <div>{children}</div>,
  Stack: ({ children }: any) => <div>{children}</div>
}));

vi.mock('@tui/core', () => ({
  PageCenter: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/elements/display/Markdown', () => ({
  default: ({ md }: any) => <div>{md}</div>
}));

vi.mock('components/elements/hit/HitOutline', () => ({
  default: ({ hit, template }: any) => <div>{`${hit.howler.id}:${template.detection}:${template.keys.join(',')}`}</div>
}));

vi.mock('components/elements/hit/HitLayout', () => ({
  HitLayout: { NORMAL: 'normal' }
}));

vi.mock('components/hooks/useScrollRestoration', () => ({
  useScrollRestoration: vi.fn()
}));

vi.mock('plugins/store', () => ({
  default: { plugins: ['demo'] }
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ i18n: { language: 'en' } })
}));

vi.mock('react-pluggable', () => ({
  usePluginStore: () => ({})
}));

vi.mock('utils/utils', async importOriginal => {
  const actual = await importOriginal<typeof import('utils/utils')>();
  return {
    ...actual,
    modifyDocumentation: mockModifyDocumentation
  };
});

vi.mock('./markdown/en/templates.md', () => ({
  default: 'intro $CURRENT_URL $ALERT_1\n===SPLIT===\noutro $ALERT_2'
}));
vi.mock('./markdown/fr/templates.md', () => ({
  default: 'fr-intro\n===SPLIT===\nfr-outro'
}));

import TemplateDocumentation from './TemplateDocumentation';

describe('TemplateDocumentation', () => {
  it('renders both markdown sections and sample hit outlines', () => {
    render(<TemplateDocumentation />);

    expect(screen.getByText(/modified:intro/)).toHaveTextContent(window.location.origin);
    expect(screen.getByText(/modified:outro/)).toBeInTheDocument();
    expect(screen.getByText(/hit1:Listening for Meows:event.start,event.end,event.kind,event.outcome/)).toBeInTheDocument();
    expect(screen.getByText(/hit2:Looking for paw prints:event.start,event.end,event.provider,event.reason/)).toBeInTheDocument();
    expect(mockModifyDocumentation).toHaveBeenCalledTimes(2);
  });
});
