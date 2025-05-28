import type { Monaco } from '@monaco-editor/react';
import { useMonaco } from '@monaco-editor/react';
import { useTheme } from '@mui/material';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import ThemedEditor from 'components/elements/ThemedEditor';
import type { editor } from 'monaco-editor';
import { memo, useCallback, useContext, useEffect, useMemo, type FC } from 'react';
import { conf, language } from './markdownExtendedTokenProvider';

interface OverviewEditorProps {
  content: string;
  setContent: (content: string) => void;
  onMount?: () => void;
  fontSize?: number;
  height?: string;
  width?: string;
  editorOptions?: editor.IStandaloneEditorConstructionOptions;
}

const OverviewEditor: FC<OverviewEditorProps> = ({
  content,
  setContent,
  onMount,
  fontSize = 16,
  height = '100%',
  width = '100%',
  editorOptions = {}
}) => {
  const theme = useTheme();
  const monaco = useMonaco();
  const { config } = useContext(ApiConfigContext);

  const beforeEditorMount = useCallback((_monaco: Monaco) => {
    _monaco.languages.register({ id: 'markdown-extended' });
    _monaco.languages.setLanguageConfiguration('markdown-extended', conf);
    _monaco.languages.setMonarchTokensProvider('markdown-extended', language);
  }, []);

  useEffect(() => {
    if (!monaco) {
      return;
    }

    monaco.editor.getModels().forEach(model => model.setEOL(monaco.editor.EndOfLineSequence.LF));

    if (monaco.languages.getLanguages().some(lang => lang.id === 'markdown-extended')) {
      // Set the parsers
      const confDisposable = monaco.languages.setLanguageConfiguration('markdown-extended', conf);
      const languageDisposable = monaco.languages.setMonarchTokensProvider('markdown-extended', language);

      return () => {
        confDisposable?.dispose();
        languageDisposable?.dispose();
      };
    }
  }, [config.lookups, monaco]);

  useEffect(() => {
    if (!monaco) {
      return;
    }

    const disposable = monaco.editor.onDidCreateModel(model => {
      monaco.editor.setModelLanguage(model, 'markdown-extended');
    });

    monaco.editor.getModels().forEach(model => {
      monaco.editor.setModelLanguage(model, 'markdown-extended');
    });

    return disposable.dispose;
  }, [monaco]);

  const options: editor.IStandaloneEditorConstructionOptions = useMemo(
    () => ({
      fontSize,
      bracketPairColorization: {
        enabled: false
      },
      scrollbar: {
        horizontal: 'auto'
      },
      ...editorOptions
    }),
    [fontSize, editorOptions]
  );

  return (
    <ThemedEditor
      height={height}
      width={width}
      theme={theme.palette.mode === 'light' ? 'howler' : 'howler-dark'}
      value={content}
      onChange={value => setContent(value)}
      beforeMount={beforeEditorMount}
      onMount={onMount}
      options={options}
    />
  );
};

export default memo(OverviewEditor);
