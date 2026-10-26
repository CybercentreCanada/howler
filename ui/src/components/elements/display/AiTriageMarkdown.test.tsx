/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import AiTriageMarkdown from './AiTriageMarkdown';

describe('AiTriageMarkdown', () => {
  it('renders markdown while ignoring hostile HTML and remote images', () => {
    render(
      <AiTriageMarkdown
        md={
          '# AI summary\n\n{{hit.id}}\n\n![remote image](https://example.invalid/image.png)\n\n<img src="x" onerror="alert(1)" />\n\n<script>alert(1)</script>\n\n[unsafe link](javascript:alert(1))\n\n```mermaid\ngraph TD; A-->B\n```'
        }
      />
    );

    expect(screen.getByRole('heading', { name: 'AI summary' })).toBeInTheDocument();
    expect(screen.getByText('{{hit.id}}')).toBeInTheDocument();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(document.querySelector('script')).toBeNull();
    expect(document.querySelector('[onerror]')).toBeNull();
    expect(document.querySelector('a[href^="javascript:"]')).toBeNull();
    expect(document.querySelector('.mermaid')).toBeNull();
  });
});
