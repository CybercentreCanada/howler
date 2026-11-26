import { hstream, joinAllUri } from 'api';
import { uri as parentUri } from 'api/v2/ai';

export type AiLuceneRequest = {
  prompt: string;
  query?: string;
};

export type AiLuceneOptions = {
  /** Called with the full text generated so far, which may replace earlier text. */
  onText?: (text: string) => void;
  /** Called with agent progress messages, such as tool calls. */
  onStatus?: (status: string) => void;
  signal?: AbortSignal;
};

export type AiLuceneResult = {
  query: string;
  /** Set when the generated query is not valid Lucene. */
  warning?: string;
};

type AiLuceneEventData = {
  text?: string;
  status?: string;
  query?: string;
  warning?: string;
  error?: string;
};

export const uri = () => {
  return joinAllUri(parentUri(), 'lucene');
};

/**
 * Stream a Lucene query generated from a natural-language prompt.
 *
 * @returns the final cleaned query, and a warning when it is not valid Lucene, once generation completes.
 */
export const post = async (
  request: AiLuceneRequest,
  { onText, onStatus, signal }: AiLuceneOptions = {}
): Promise<AiLuceneResult> => {
  let result: AiLuceneResult | undefined;

  await hstream(
    uri(),
    request,
    ({ event, data }) => {
      const payload = (data ?? {}) as AiLuceneEventData;

      if (event === 'error') {
        throw new Error(payload.error || 'AI query generation failed.');
      }

      if (event === 'done') {
        result = { query: payload.query ?? '', warning: payload.warning };
      } else if (event === 'status') {
        onStatus?.(payload.status ?? '');
      } else if (typeof payload.text === 'string') {
        onText?.(payload.text);
      }
    },
    signal
  );

  if (!result) {
    throw new Error('AI query generation ended unexpectedly.');
  }

  return result;
};
