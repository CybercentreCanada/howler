import type { EditorProps, Monaco } from '@monaco-editor/react';
import { Editor, useMonaco } from '@monaco-editor/react';
import { useTheme } from '@mui/material';
import type { AppThemeConfigs } from 'commons/components/app/AppConfigs';
import useThemeBuilder from 'commons/components/utils/hooks/useThemeBuilder';
import useMyTheme from 'components/hooks/useMyTheme';
import type { editor } from 'monaco-editor';
import { memo, useCallback, useEffect, useMemo, type FC } from 'react';

const ThemedEditor: FC<EditorProps> = ({ beforeMount, options = {}, ...otherProps }) => {
  const myTheme: AppThemeConfigs = useMyTheme();
  const themeBuilder = useThemeBuilder(myTheme);
  const theme = useTheme();
  const monaco = useMonaco();

  const _beforeMount = useCallback(
    (_monaco: Monaco) => {
      let lightBackground = themeBuilder.lightTheme.palette.background.paper;
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
            foreground: themeBuilder.lightTheme.palette.warning.dark.toUpperCase().replaceAll('#', '')
          },
          {
            token: 'operator',
            foreground: themeBuilder.lightTheme.palette.warning.light.toUpperCase().replaceAll('#', '')
          },
          {
            token: 'string.invalid',
            foreground: themeBuilder.lightTheme.palette.error.main.toUpperCase().replaceAll('#', '')
          },
          {
            token: 'invalid',
            foreground: themeBuilder.lightTheme.palette.error.main.toUpperCase().replaceAll('#', '')
          },
          {
            token: 'boolean',
            foreground: themeBuilder.lightTheme.palette.success.main.toUpperCase().replaceAll('#', '')
          }
        ],
        colors: {
          'editor.background': lightBackground
        }
      });

      let darkBackground = themeBuilder.darkTheme.palette.background.paper;
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
            foreground: themeBuilder.darkTheme.palette.warning.dark.toUpperCase().replaceAll('#', '')
          },
          {
            token: 'operator',
            foreground: themeBuilder.darkTheme.palette.warning.light.toUpperCase().replaceAll('#', '')
          },
          {
            token: 'string.invalid',
            foreground: themeBuilder.darkTheme.palette.error.main.toUpperCase().replaceAll('#', '')
          },
          {
            token: 'invalid',
            foreground: themeBuilder.darkTheme.palette.error.main.toUpperCase().replaceAll('#', '')
          },
          {
            token: 'boolean',
            foreground: themeBuilder.darkTheme.palette.success.main.toUpperCase().replaceAll('#', '')
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
    [beforeMount, themeBuilder]
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
      theme={theme.palette.mode === 'light' ? 'howler' : 'howler-dark'}
      beforeMount={_beforeMount}
      options={_options}
    />
  );
};

export default memo(ThemedEditor);
