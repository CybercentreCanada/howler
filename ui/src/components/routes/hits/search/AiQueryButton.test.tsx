/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import type { FC } from 'react';
import { useState } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockLucenePost = vi.hoisted(() => vi.fn());
const mockShowErrorMessage = vi.hoisted(() => vi.fn());
const mockShowWarningMessage = vi.hoisted(() => vi.fn());

vi.mock('api', () => ({
  default: { v2: { ai: { lucene: { post: mockLucenePost } } } }
}));

vi.mock('components/hooks/useMySnackbar', () => ({
  default: () => ({ showErrorMessage: mockShowErrorMessage, showWarningMessage: mockShowWarningMessage })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

import AiQueryButton from './AiQueryButton';

const Harness: FC<{ enabled?: boolean }> = ({ enabled = true }) => {
  const [query, setQuery] = useState('howler.status:open');

  return (
    <ApiConfigContext.Provider
      value={{
        config: { configuration: { features: { ai_lucene: enabled } } as any },
        setConfig: vi.fn(),
        loaded: true
      }}
    >
      <div id="current-query">{query}</div>
      <AiQueryButton query={query} setQuery={setQuery} />
    </ApiConfigContext.Provider>
  );
};

const submitPrompt = (prompt: string) => {
  fireEvent.click(screen.getByTestId('ai-query-button'));
  fireEvent.change(screen.getByRole('textbox'), { target: { value: prompt } });
  fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Enter' });
};

describe('AiQueryButton', () => {
  beforeEach(() => {
    mockLucenePost.mockReset();
    mockShowErrorMessage.mockReset();
    mockShowWarningMessage.mockReset();
  });

  it('is hidden when AI query generation is disabled', () => {
    render(<Harness enabled={false} />);

    expect(screen.queryByTestId('ai-query-button')).not.toBeInTheDocument();
  });

  it('streams generated text into the query and applies the final query', async () => {
    let finish: (result: { query: string; warning?: string }) => void = () => undefined;
    mockLucenePost.mockImplementation((_request, { onText, onStatus }) => {
      onStatus('Checking fields');
      onText('draft');
      onText('howler.escalation:alert');
      return new Promise(resolve => {
        finish = resolve;
      });
    });

    render(<Harness />);
    submitPrompt(' escalated alerts ');

    await waitFor(() => expect(screen.getByTestId('current-query')).toHaveTextContent(/^howler\.escalation:alert$/));
    expect(screen.getByTestId('ai-query-progress')).toBeInTheDocument();
    expect(mockLucenePost).toHaveBeenCalledWith(
      { prompt: 'escalated alerts', query: 'howler.status:open' },
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );

    finish({ query: 'howler.status:open AND howler.escalation:alert', warning: 'Check it' });

    await waitFor(() =>
      expect(screen.getByTestId('current-query')).toHaveTextContent('howler.status:open AND howler.escalation:alert')
    );
    expect(mockShowWarningMessage).toHaveBeenCalledWith('Check it');
    expect(screen.queryByTestId('ai-query-progress')).not.toBeInTheDocument();
  });

  it('restores the original query and reports generation errors', async () => {
    mockLucenePost.mockImplementation(async (_request, { onText }) => {
      onText('partial');
      throw new Error('Provider response timed out');
    });

    render(<Harness />);
    submitPrompt('anything');

    await waitFor(() => expect(mockShowErrorMessage).toHaveBeenCalledWith('Provider response timed out'));
    expect(screen.getByTestId('current-query')).toHaveTextContent('howler.status:open');
  });

  it('stops generation without reporting an error', async () => {
    mockLucenePost.mockImplementation(
      (_request, { onText, signal }) =>
        new Promise((_resolve, reject) => {
          onText('partial');
          signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
        })
    );

    render(<Harness />);
    submitPrompt('anything');

    await waitFor(() => expect(screen.getByTestId('current-query')).toHaveTextContent('partial'));
    fireEvent.click(screen.getByTestId('ai-query-button'));

    await waitFor(() => expect(screen.getByTestId('current-query')).toHaveTextContent('howler.status:open'));
    expect(mockShowErrorMessage).not.toHaveBeenCalled();
  });
});
