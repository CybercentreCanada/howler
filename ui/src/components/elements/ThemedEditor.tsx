import type { EditorProps, Monaco } from '@monaco-editor/react';
import { Editor, useMonaco } from '@monaco-editor/react';
import { useTheme } from '@mui/material';
import { useAppTheme, useAppThemeBuilder } from '@tui/core';
import type { editor } from 'monaco-editor';
import { memo, useCallback, useEffect, useMemo, type FC } from 'react';

const ThemedEditor: FC<EditorProps & { id?: string }> = ({ beforeMount, options = {}, id, ...otherProps }) => {
  const { current: currentTheme, optionsOverride } = useAppTheme();
  const themeBuilder = useAppThemeBuilder();
  const { lightTheme, darkTheme } = useMemo(
    () => themeBuilder(currentTheme, optionsOverride),
    [themeBuilder, currentTheme, optionsOverride]
  );
  const theme = useTheme();
  const monaco = useMonaco();

  const _beforeMount = useCallback(
    (_monaco: Monaco) => {
      let lightBackground = lightTheme.palette.background.paper;
      // monaco doesn't like colours in the form #fff, with only three digits.
      if (lightBackground.startsWith('#') && lightBackground.length < 7) {
        lightBackground = lightBackground.replace(/(\w)/g, '$1$1');
      }

      _monaco.editor.defineTheme('howler', {
        base: 'vs',
        inherit: true,
        rules: [
          {
            token: 'handlebars',
            foreground: lightTheme.palette.warning.dark.toUpperCase().replaceAll('#', '')
          },
          {
            token: 'operator',
            foreground: lightTheme.palette.warning.light.toUpperCase().replaceAll('#', '')
          },
          {
            token: 'string.invalid',
            foreground: lightTheme.palette.error.main.toUpperCase().replaceAll('#', '')
          },
          {
            token: 'invalid',
            foreground: lightTheme.palette.error.main.toUpperCase().replaceAll('#', '')
          },
          {
            token: 'boolean',
            foreground: lightTheme.palette.success.main.toUpperCase().replaceAll('#', '')
          }
        ],
        colors: {
          'editor.background': lightBackground
        }
      });

      let darkBackground = darkTheme.palette.background.paper;
      // monaco doesn't like colours in the form #fff, with only three digits.
      if (darkBackground.startsWith('#') && darkBackground.length < 7) {
        darkBackground = darkBackground.replace(/(\w)/g, '$1$1');
      }
      _monaco.editor.defineTheme('howler-dark', {
        base: 'vs-dark',
        inherit: true,
        rules: [
          {
            token: 'handlebars',
            foreground: darkTheme.palette.warning.dark.toUpperCase().replaceAll('#', '')
          },
          {
            token: 'operator',
            foreground: darkTheme.palette.warning.light.toUpperCase().replaceAll('#', '')
          },
          {
            token: 'string.invalid',
            foreground: darkTheme.palette.error.main.toUpperCase().replaceAll('#', '')
          },
          {
            token: 'invalid',
            foreground: darkTheme.palette.error.main.toUpperCase().replaceAll('#', '')
          },
          {
            token: 'boolean',
            foreground: darkTheme.palette.success.main.toUpperCase().replaceAll('#', '')
          }
        ],
        colors: {
          'editor.background': darkBackground
        }
      });

      _monaco.languages.register({ id: 'lucene' });
      _monaco.languages.register({ id: 'eql' });

      beforeMount?.(_monaco);
    },
    [beforeMount, lightTheme, darkTheme]
  );

  useEffect(() => {
    if (!monaco) {
      return;
    }

    monaco.editor.setTheme(theme.palette.mode === 'light' ? 'howler' : 'howler-dark');
  }, [monaco, theme.palette.background.paper, theme.palette.mode]);

  const _options: editor.IStandaloneEditorConstructionOptions = useMemo(
    () => ({
      automaticLayout: true,
      minimap: { enabled: false },
      overviewRulerBorder: false,
      renderLineHighlight: 'gutter',
      autoClosingBrackets: 'always',
      scrollbar: {
        horizontal: 'hidden'
      },
      ...options
    }),
    [options]
  );

  return (
    <Editor
      {...otherProps}
      wrapperProps={{ id }}
      theme={theme.palette.mode === 'light' ? 'howler' : 'howler-dark'}
      beforeMount={_beforeMount}
      options={_options}
    />
  );
};

export default memo(ThemedEditor);
