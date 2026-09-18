/// <reference types="vitest" />
import { fireEvent, render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

const mockLuceneCompletion = vi.hoisted(() => ({ provideCompletionItems: vi.fn() }));
const mockYamlCompletion = vi.hoisted(() => ({ provideCompletionItems: vi.fn() }));
const mockEqlCompletion = vi.hoisted(() => ({ provideCompletionItems: vi.fn() }));
const mockHistoryCompletion = vi.hoisted(() => ({ provideCompletionItems: vi.fn() }));
const mockSetFzfSearch = vi.hoisted(() => vi.fn());
const mockSetModelLanguage = vi.hoisted(() => vi.fn());
const mockRegisterCompletionItemProvider = vi.hoisted(() => vi.fn(() => ({ dispose: vi.fn() })));
const mockSetMonarchTokensProvider = vi.hoisted(() => vi.fn(() => ({ dispose: vi.fn() })));
const mockRegisterLanguage = vi.hoisted(() => vi.fn());
const mockOnDidCreateModel = vi.hoisted(() => vi.fn(() => ({ dispose: vi.fn() })));
const mockEditorProps = vi.hoisted(() => ({ current: null as any }));

let mockFzfSearch = false;
let mockMonaco: any = null;

vi.mock('@monaco-editor/react', () => ({
  useMonaco: () => mockMonaco
}));

vi.mock('@mui/material', () => ({
  Box: ({ children, onKeyDownCapture }: any) => <div onKeyDownCapture={onKeyDownCapture}>{children}</div>,
  useTheme: () => ({ palette: { mode: 'light' } })
}));

vi.mock('components/app/providers/ApiConfigProvider', () => ({
  ApiConfigContext: {}
}));

vi.mock('components/app/providers/RecordSearchProvider', () => ({
  RecordSearchContext: {}
}));

vi.mock('components/elements/ThemedEditor', () => ({
  default: (props: any) => {
    mockEditorProps.current = props;
    return <div id={props.wrapperProps?.id}>editor</div>;
  }
}));

vi.mock('use-context-selector', () => ({
  useContextSelector: (_context: unknown, selector: (ctx: any) => any) =>
    selector({ fzfSearch: mockFzfSearch, setFzfSearch: mockSetFzfSearch })
}));

vi.mock('./eqlCompletionProvider', () => ({
  default: () => mockEqlCompletion
}));

vi.mock('./historyCompletionProvider', () => ({
  default: () => mockHistoryCompletion
}));

vi.mock('./luceneCompletionProvider', () => ({
  default: () => mockLuceneCompletion
}));

vi.mock('./yamlCompletionProvider', () => ({
  default: () => mockYamlCompletion
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: () => ({ config: { lookups: { status: ['open'] } } })
  };
});

import QueryEditor from './QueryEditor';

describe('QueryEditor', () => {
  afterEach(() => {
    mockFzfSearch = false;
    mockEditorProps.current = null;
    vi.clearAllMocks();
  });

  it('registers languages, completion providers, and editor language handlers', () => {
    const textModel = {
      setEOL: vi.fn(),
      getLanguageId: vi.fn(() => 'plaintext')
    };
    const markdownModel = {
      setEOL: vi.fn(),
      getLanguageId: vi.fn(() => 'markdown')
    };
    mockMonaco = {
      languages: {
        register: mockRegisterLanguage,
        registerCompletionItemProvider: mockRegisterCompletionItemProvider,
        setMonarchTokensProvider: mockSetMonarchTokensProvider
      },
      editor: {
        EndOfLineSequence: { LF: 0 },
        getModels: () => [textModel, markdownModel],
        onDidCreateModel: mockOnDidCreateModel,
        setModelLanguage: mockSetModelLanguage
      }
    };

    const onMount = vi.fn();
    const setQuery = vi.fn();
    const { unmount } = render(<QueryEditor id="query-editor" query="a:b" setQuery={setQuery} onMount={onMount} />);

    mockEditorProps.current.beforeMount(mockMonaco);

    expect(mockRegisterLanguage).toHaveBeenCalledWith({ id: 'lucene' });
    expect(mockRegisterLanguage).toHaveBeenCalledWith({ id: 'eql' });
    expect(mockSetMonarchTokensProvider).toHaveBeenCalledTimes(2);
    expect(mockRegisterCompletionItemProvider).toHaveBeenCalledWith('lucene', mockLuceneCompletion);
    expect(mockRegisterCompletionItemProvider).toHaveBeenCalledWith('yaml', mockYamlCompletion);
    expect(mockRegisterCompletionItemProvider).toHaveBeenCalledWith('eql', mockEqlCompletion);
    expect(textModel.setEOL).toHaveBeenCalledWith(0);
    expect(mockSetModelLanguage).toHaveBeenCalledWith(textModel, 'lucene');
    expect(mockSetModelLanguage).not.toHaveBeenCalledWith(markdownModel, 'lucene');
    expect(mockEditorProps.current.options).toMatchObject({ readOnly: false, fontSize: 16 });
    expect(mockEditorProps.current.theme).toBe('howler');

    mockEditorProps.current.onChange('field:value');
    expect(setQuery).toHaveBeenCalledWith('field:value');

    unmount();
  });

  it('switches to history completion and toggles fzf mode with ctrl+r', () => {
    mockFzfSearch = true;
    mockMonaco = {
      languages: {
        register: mockRegisterLanguage,
        registerCompletionItemProvider: mockRegisterCompletionItemProvider,
        setMonarchTokensProvider: mockSetMonarchTokensProvider
      },
      editor: {
        EndOfLineSequence: { LF: 0 },
        getModels: () => [],
        onDidCreateModel: mockOnDidCreateModel,
        setModelLanguage: mockSetModelLanguage
      }
    };

    const setQuery = vi.fn();
    const { container } = render(<QueryEditor query="test" setQuery={setQuery} fontSize={18} editorOptions={{ wordWrap: 'on' }} />);

    expect(mockRegisterCompletionItemProvider).toHaveBeenCalledWith('lucene', mockHistoryCompletion);
    expect(mockRegisterCompletionItemProvider).not.toHaveBeenCalledWith('yaml', mockYamlCompletion);
    expect(mockEditorProps.current.options).toMatchObject({ readOnly: false, fontSize: 18, wordWrap: 'on' });

    fireEvent.keyDown(container.firstChild as Element, { ctrlKey: true, key: 'r' });
    expect(mockSetFzfSearch).toHaveBeenCalledWith(false);
  });
});
