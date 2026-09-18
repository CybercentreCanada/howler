/// <reference types="vitest" />
import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const apiConfigContextToken = vi.hoisted(() => ({ name: 'api-config-context' }));
const capturedProps = vi.hoisted(() => ({ current: null as any }));

let monacoValue: any = null;

vi.mock('@monaco-editor/react', () => ({
  useMonaco: () => monacoValue
}));

vi.mock('@mui/material', () => ({
  useTheme: () => ({ palette: { mode: 'light' } })
}));

vi.mock('components/app/providers/ApiConfigProvider', () => ({
  ApiConfigContext: apiConfigContextToken
}));

vi.mock('components/elements/ThemedEditor', () => ({
  default: (props: any) => {
    capturedProps.current = props;
    return <div>themed-editor</div>;
  }
}));

vi.mock('../routes/overviews/markdownExtendedTokenProvider', () => ({
  conf: { autoClosingPairs: [] },
  language: { tokenizer: {} }
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === apiConfigContextToken) return { config: { lookups: {} } };
      return actual.useContext(context);
    }
  };
});

import MarkdownEditor from './MarkdownEditor';

describe('MarkdownEditor', () => {
  it('configures markdown-extended editors and normalizes onChange values', () => {
    const setEOL = vi.fn();
    const model = { setEOL, getLanguageId: () => 'plaintext' };
    const dispose = vi.fn();
    monacoValue = {
      editor: {
        EndOfLineSequence: { LF: 1 },
        getModels: () => [model],
        onDidCreateModel: (cb: any) => {
          cb(model);
          return { dispose };
        },
        setModelLanguage: vi.fn()
      },
      languages: {
        register: vi.fn(),
        setLanguageConfiguration: vi.fn(() => ({ dispose })),
        setMonarchTokensProvider: vi.fn(() => ({ dispose })),
        getLanguages: () => [{ id: 'markdown-extended' }]
      }
    };

    const setContent = vi.fn();
    render(<MarkdownEditor content="hello" setContent={setContent} editorOptions={{ wordWrap: 'on' }} />);

    capturedProps.current.beforeMount(monacoValue);
    expect(monacoValue.languages.register).toHaveBeenCalledWith({ id: 'markdown-extended' });
    expect(setEOL).toHaveBeenCalledWith(1);
    expect(monacoValue.editor.setModelLanguage).toHaveBeenCalledWith(model, 'markdown-extended');
    expect(capturedProps.current.options).toMatchObject({
      fontSize: 16,
      wordWrap: 'on',
      bracketPairColorization: { enabled: false }
    });

    capturedProps.current.onChange(undefined);
    expect(setContent).toHaveBeenCalledWith('');
  });
});
