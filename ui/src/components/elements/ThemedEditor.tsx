import type { EditorProps, Monaco } from '@monaco-editor/react';
import { Editor, useMonaco } from '@monaco-editor/react';
import { useTheme } from '@mui/material';
import type { editor } from 'monaco-editor';
import { memo, useCallback, useEffect, useMemo, type FC } from 'react';

const toMonacoColor = (color: string): string => {
  const trimmedColor = color.trim();
  const hexMatch = trimmedColor.match(/^#?([\da-f]{3,4}|[\da-f]{6}|[\da-f]{8})$/i);
  if (hexMatch) {
    let hex = hexMatch[1] ?? '';
    if (hex.length === 3 || hex.length === 4) {
      hex = hex
        .split('')
        .map(character => character.repeat(2))
        .join('');
    }

    return `#${hex.toUpperCase()}`;
  }

  const rgbMatch = trimmedColor.match(/^rgba?\((.*)\)$/i);
  if (!rgbMatch) {
    return trimmedColor;
  }

  const [channelValues = '', slashAlpha] = (rgbMatch[1] ?? '').split('/');
  const channels = channelValues
    .split(/[\s,]+/)
    .filter(Boolean)
    .map(channel => channel.trim());
  const alpha = slashAlpha?.trim() ?? (channels.length > 3 ? channels.pop() : undefined);

  if (channels.length === 3 && channels.every(channel => /^-?(?:\d+\.?\d*|\.\d+)%?$/.test(channel))) {
    return trimmedColor;
  }

  const hexChannels = channels
    .map(channel => {
      const amount = Number.parseFloat(channel);
      const value = channel.endsWith('%') ? (amount * 255) / 100 : amount;
      return Math.round(Math.min(255, Math.max(0, value)))
        .toString(16)
        .padStart(2, '0');
    })
    .join('');

  if (!alpha) {
    return `#${hexChannels.toUpperCase()}`;
  }

  const alphaValue = Number.parseFloat(alpha);
  if (/^-?(?:\d+\.?\d*|\.\d+)%?$/.test(alpha)) {
    const normalizedAlpha = alpha.endsWith('%') ? alphaValue / 100 : alphaValue;
    const alphaHex = Math.round(Math.min(1, Math.max(0, normalizedAlpha)) * 255)
      .toString(16)
      .padStart(2, '0');
    return `#${hexChannels}${alphaHex}`.toUpperCase();
  }

  return trimmedColor;
};

const toMonacoTokenColor = (color: string) => toMonacoColor(color).replace(/^#/, '');

const ThemedEditor: FC<EditorProps & { id?: string }> = ({ beforeMount, options = {}, id, ...otherProps }) => {
  const theme = useTheme();
  const monaco = useMonaco();

  const monacoTheme: editor.IStandaloneThemeData = useMemo(
    () => ({
      base: theme.palette.mode === 'light' ? 'vs' : 'vs-dark',
      inherit: true,
      rules: [
        {
          token: 'handlebars',
          foreground: toMonacoTokenColor(theme.palette.warning.dark)
        },
        {
          token: 'operator',
          foreground: toMonacoTokenColor(theme.palette.warning.light)
        },
        {
          token: 'string.invalid',
          foreground: toMonacoTokenColor(theme.palette.error.main)
        },
        {
          token: 'invalid',
          foreground: toMonacoTokenColor(theme.palette.error.main)
        },
        {
          token: 'boolean',
          foreground: toMonacoTokenColor(theme.palette.success.main)
        }
      ],
      colors: {
        'editor.background': toMonacoColor(theme.palette.background.paper),
        'editor.foreground': toMonacoColor(theme.palette.text.primary),
        'editorGutter.background': toMonacoColor(theme.palette.background.paper),
        'editorLineNumber.foreground': toMonacoColor(theme.palette.text.disabled),
        'editorLineNumber.activeForeground': toMonacoColor(theme.palette.text.secondary),
        'editorCursor.foreground': toMonacoColor(theme.palette.primary.main),
        'editor.selectionBackground': toMonacoColor(theme.palette.action.selected),
        'editor.inactiveSelectionBackground': toMonacoColor(theme.palette.action.hover),
        'editor.lineHighlightBackground': toMonacoColor(theme.palette.action.hover),
        'editorWhitespace.foreground': toMonacoColor(theme.palette.divider),
        'editorIndentGuide.background': toMonacoColor(theme.palette.divider),
        'editorIndentGuide.activeBackground': toMonacoColor(theme.palette.text.disabled),
        'editorWidget.background': toMonacoColor(theme.palette.background.paper),
        'editorWidget.border': toMonacoColor(theme.palette.divider),
        'editorSuggestWidget.background': toMonacoColor(theme.palette.background.paper),
        'editorSuggestWidget.border': toMonacoColor(theme.palette.divider),
        'editorSuggestWidget.selectedBackground': toMonacoColor(theme.palette.action.selected),
        'editorHoverWidget.background': toMonacoColor(theme.palette.background.paper),
        'editorHoverWidget.border': toMonacoColor(theme.palette.divider),
        'editorOverviewRuler.border': toMonacoColor(theme.palette.divider),
        'scrollbarSlider.background': toMonacoColor(theme.palette.action.hover),
        'scrollbarSlider.hoverBackground': toMonacoColor(theme.palette.action.selected),
        'scrollbarSlider.activeBackground': toMonacoColor(theme.palette.action.active)
      }
    }),
    [theme]
  );

  const _beforeMount = useCallback(
    (_monaco: Monaco) => {
      _monaco.editor.defineTheme('howler', monacoTheme);

      _monaco.languages.register({ id: 'lucene' });
      _monaco.languages.register({ id: 'eql' });

      beforeMount?.(_monaco);
    },
    [beforeMount, monacoTheme]
  );

  useEffect(() => {
    if (!monaco) {
      return;
    }

    monaco.editor.defineTheme('howler', monacoTheme);
    monaco.editor.setTheme('howler');
  }, [monaco, monacoTheme]);

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

  return <Editor {...otherProps} wrapperProps={{ id }} theme="howler" beforeMount={_beforeMount} options={_options} />;
};

export default memo(ThemedEditor);
