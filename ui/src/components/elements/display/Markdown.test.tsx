import { render, screen } from '@testing-library/react';
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
    const { container } = render(<Markdown untrusted disableLinks md={md} />);

    expect(container.querySelector('img')).toBeNull();
    expect(container.querySelector('[onerror]')).toBeNull();
    expect(container.querySelector('a[href*="attacker.invalid"]')).toBeNull();
    expect(container.querySelector('a[href^="//"]')).toBeNull();
  });
});
