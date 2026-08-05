import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import Markdown from './Markdown';

vi.mock('commons/components/app/hooks', () => ({
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
});
