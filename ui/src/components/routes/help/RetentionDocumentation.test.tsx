/// <reference types="vitest" />
import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const mockHitSearch = vi.hoisted(() => vi.fn());
const mockModifyDocumentation = vi.hoisted(() => vi.fn((md: string) => `retention:${md.slice(0, 10)}`));

vi.mock('@tui/core', () => ({
  PageCenter: ({ children }: any) => <div>{children}</div>
}));

vi.mock('api', () => ({
  default: {
    search: {
      hit: {
        post: mockHitSearch
      }
    }
  }
}));

vi.mock('components/elements/display/Markdown', () => ({
  default: ({ md, components }: { md: string; components?: Record<string, React.ReactNode> }) => (
    <div>
      <div>{md}</div>
      <div>{components?.duration}</div>
      <div>{components?.alert}</div>
    </div>
  )
}));

vi.mock('components/elements/hit/HitCard', () => ({
  default: ({ id }: { id: string }) => <div>hit:{id}</div>
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

import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import RetentionDocumentation from './RetentionDocumentation';

describe('RetentionDocumentation', () => {
  it('renders retention values and the fetched example alert card', async () => {
    mockHitSearch.mockResolvedValue({ items: [{ howler: { id: 'hit-1' } }] });

    render(
      <ApiConfigContext.Provider
        value={{
          config: {
            configuration: {
              system: {
                retention: {
                  limit_amount: 90,
                  limit_unit: 'days'
                }
              }
            }
          }
        } as any}
      >
        <RetentionDocumentation />
      </ApiConfigContext.Provider>
    );

    expect(screen.getByText(/^retention:/)).toBeInTheDocument();
    expect(screen.getByText('90 days')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('hit:hit-1')).toBeInTheDocument());
  });
});
