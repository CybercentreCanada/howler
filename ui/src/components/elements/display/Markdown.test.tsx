/** @vitest-environment-options {"url": "https://howler.test/hits/hit-1"} */

import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import Markdown from './Markdown';

vi.mock('@tui/core', () => ({
  useAppTheme: () => ({ isDark: false })
}));

vi.mock('mermaid', () => ({
  default: {
    initialize: vi.fn(),
    run: vi.fn()
  }
}));

vi.mock('./Notebook', () => ({
  Notebook: () => null
}));

vi.mock('./json/JSONViewer', () => ({
  default: ({ data, hideSearch }: { data: object; hideSearch: boolean }) => (
    <output id="json-viewer">{JSON.stringify({ data, hideSearch })}</output>
  )
}));

describe('Markdown', () => {
  it('forwards hideSearch from JSON fence options to the viewer', () => {
    render(<Markdown md={'```json[hideSearch=true]\n{"value":"visible"}\n```'} />);

    expect(screen.getByTestId('json-viewer')).toHaveTextContent(
      JSON.stringify({ data: { value: 'visible' }, hideSearch: true })
    );
  });

  it('renders untrusted markdown without raw HTML, images, or external links', () => {
    const md = [
      '<img src="https://attacker.invalid/raw" onerror="alert(1)" />',
      '![remote](https://attacker.invalid/image)',
      '[external](https://attacker.invalid/page)',
      '[protocol relative](//evil.com)'
    ].join('\n\n');
    const { container } = render(
      <MemoryRouter>
        <Markdown untrusted disableLinks md={md} />
      </MemoryRouter>
    );

    expect(container.querySelector('img')).toBeNull();
    expect(container.querySelector('[onerror]')).toBeNull();
    expect(container.querySelector('a[href*="attacker.invalid"]')).toBeNull();
    expect(container.querySelector('a[href^="//"]')).toBeNull();
  });

  it.each([
    {
      name: 'a raw backslash destination',
      md: String.raw`[test](/\attacker.invalid/path)`,
      expectedHref: '/%5Cattacker.invalid/path'
    },
    {
      name: 'an angle-bracket backslash destination',
      md: String.raw`[test](</\attacker.invalid/path>)`,
      expectedHref: '/%5Cattacker.invalid/path'
    },
    {
      name: 'a percent-encoded backslash destination',
      md: '[test](/%5Cattacker.invalid/path)',
      expectedHref: '/%5Cattacker.invalid/path'
    },
    {
      name: 'an angle-bracket tab destination',
      md: '[test](</\t/attacker.invalid/path>)',
      expectedHref: '/%09/attacker.invalid/path'
    },
    {
      name: 'a percent-encoded tab destination',
      md: '[test](/%09/attacker.invalid/path)',
      expectedHref: '/%09/attacker.invalid/path'
    },
    {
      name: 'a root-relative hit link',
      md: '[test](/hits/hit-1)',
      expectedHref: '/hits/hit-1'
    },
    {
      name: 'a fragment link',
      md: '[test](#summary)',
      expectedHref: '#summary'
    }
  ])('keeps $name on the application origin in untrusted markdown with links disabled', ({ md, expectedHref }) => {
    render(
      <MemoryRouter initialEntries={['/hits/hit-1']}>
        <Markdown untrusted disableLinks md={md} />
      </MemoryRouter>
    );

    const link = screen.getByRole<HTMLAnchorElement>('link', { name: 'test' });

    expect(link).toHaveAttribute('href', expectedHref);
    expect(window.location.origin).toBe('https://howler.test');
    expect(new URL(link.href).origin).toBe(window.location.origin);
  });

  it('removes protocol-relative destinations in untrusted markdown with links disabled', () => {
    render(
      <MemoryRouter>
        <Markdown untrusted disableLinks md="[protocol relative](//attacker.invalid/path)" />
      </MemoryRouter>
    );

    const link = screen.getByText<HTMLAnchorElement>('protocol relative');

    expect(screen.queryByRole('link', { name: 'protocol relative' })).not.toBeInTheDocument();
    expect(link).toHaveAttribute('href', '');
    expect(window.location.origin).toBe('https://howler.test');
    expect(new URL(link.href).origin).toBe(window.location.origin);
  });
});
