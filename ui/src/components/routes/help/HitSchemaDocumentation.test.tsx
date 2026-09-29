/// <reference types="vitest" />
import { act, fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const mockSetSearchParams = vi.hoisted(() => vi.fn());
const searchParams = new URLSearchParams();

vi.mock('@tui/core', () => ({}));

vi.mock('components/elements/display/Markdown', () => ({
  default: ({ md }: { md: string }) => <div>{md}</div>
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    i18n: { language: 'en' },
    t: (key: string) => key
  })
}));

vi.mock('react-router', () => ({
  useSearchParams: () => [searchParams, mockSetSearchParams]
}));

import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import HitSchemaDocumentation from './HitSchemaDocumentation';

const config = {
  indexes: {
    hit: {
      'howler.id': {
        type: 'keyword',
        description: 'Primary identifier',
        list: true,
        deprecated: true,
        regex: '^id-.*$',
        values: ['one', 'two'],
        deprecated_description: 'Use another field'
      },
      'event.action': {
        type: 'text',
        description: 'Action field',
        values: []
      },
      'howler.id.key_a': {
        type: 'keyword',
        description: 'shadow'
      }
    }
  }
} as any;

describe('HitSchemaDocumentation', () => {
  it('renders grouped field tables and filters them through the throttled search input', async () => {
    vi.useFakeTimers();

    render(
      <ApiConfigContext.Provider value={{ config } as any}>
        <HitSchemaDocumentation />
      </ApiConfigContext.Provider>
    );

    expect(screen.getByText('howler.id')).toBeInTheDocument();
    expect(screen.getByText('event.action')).toBeInTheDocument();
    expect(screen.getByText('list')).toBeInTheDocument();
    expect(screen.getByText('deprecated')).toBeInTheDocument();
    expect(screen.getByText('help.hit.schema.regex')).toBeInTheDocument();
    expect(screen.getByText('Use another field')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('help.hit.schema.search.prompt'), { target: { value: 'primary' } });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    });

    expect(screen.getByText('howler.id')).toBeInTheDocument();
    expect(screen.queryByText('event.action')).not.toBeInTheDocument();
    expect(mockSetSearchParams).toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button'));

    expect(screen.getByDisplayValue('')).toBeInTheDocument();
    vi.useRealTimers();
  });
});
