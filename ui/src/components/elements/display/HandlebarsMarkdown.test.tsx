/// <reference types="vitest" />
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockUseHelpers = vi.hoisted(() => vi.fn());

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('utils/Throttler', () => ({
  default: class {
    debounce(fn: () => void | Promise<void>) {
      void fn();
    }
  }
}));

vi.mock('../display/Markdown', () => ({
  __esModule: true,
  default: ({ md, disableLinks, components }: any) => (
    <div>
      <div>{md}</div>
      <div>{String(disableLinks)}</div>
      <div>{Object.keys(components).join(',')}</div>
    </div>
  )
}));

vi.mock('./handlebars/helpers', () => ({
  HowlerHelperError: class HowlerHelperError extends Error {},
  useHelpers: mockUseHelpers
}));

import HandlebarsMarkdown from './HandlebarsMarkdown';

describe('HandlebarsMarkdown', () => {
  beforeEach(() => {
    mockUseHelpers.mockReset();
  });

  it('renders markdown with synchronous helpers', async () => {
    mockUseHelpers.mockReturnValue([
      { keyword: 'hello', callback: () => 'world' }
    ]);

    render(<HandlebarsMarkdown md={'{{hello}}'} disableLinks object={{}} />);
    await waitFor(() => expect(screen.getByText('world')).toBeInTheDocument());
    expect(screen.getByText('true')).toBeInTheDocument();
  });

  it('renders helper components and missing helper fallbacks', async () => {
    mockUseHelpers.mockReturnValue([
      { keyword: 'badge', componentCallback: () => <div>component-result</div> }
    ]);

    render(<HandlebarsMarkdown md={'{{badge}}'} object={{}} />);
    await waitFor(() => expect(screen.getByText(/component-result|`/)).toBeInTheDocument());
  });
});
