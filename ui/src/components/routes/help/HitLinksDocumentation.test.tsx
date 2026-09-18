/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('components/elements/display/Markdown', () => ({
  default: ({ md }: { md: string }) => <div>{md}</div>
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ i18n: { language: 'en' } })
}));

import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import HitLinksDocumentation from './HitLinksDocumentation';

describe('HitLinksDocumentation', () => {
  it('injects configured application names into the help markdown', () => {
    render(
      <ApiConfigContext.Provider
        value={{
          config: {
            configuration: {
              ui: {
                apps: [{ name: 'Alpha' }, { name: 'Beta' }]
              }
            }
          }
        } as any}
      >
        <HitLinksDocumentation />
      </ApiConfigContext.Provider>
    );

    expect(screen.getByText(/`alpha`/)).toBeInTheDocument();
    expect(screen.getByText(/`beta`/)).toBeInTheDocument();
  });
});
