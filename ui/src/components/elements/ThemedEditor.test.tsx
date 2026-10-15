/// <reference types="vitest" />
import { render } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDefineTheme = vi.hoisted(() => vi.fn());
const mockRegisterLanguage = vi.hoisted(() => vi.fn());
const mockSetTheme = vi.hoisted(() => vi.fn());
const capturedProps = vi.hoisted(() => ({ current: null as any }));

const createPalette = (
  mode: 'light' | 'dark' = 'light',
  paper = mode === 'light' ? '#fff' : '#111',
  primary = mode === 'light' ? '#0055aa' : '#268bd2',
  foreground = mode === 'light' ? '#202020' : '#eee8d5',
  warningDark = '#abc'
) => ({
  mode,
  background: { paper },
  primary: { main: primary },
  text: { primary: foreground, secondary: '#777777', disabled: '#aaaaaa' },
  divider: '#dddddd',
  action: {
    selected: 'rgba(10, 20, 30, 0.2)',
    hover: 'rgba(10, 20, 30, 0.1)',
    active: 'rgba(10, 20, 30, 0.3)'
  },
  warning: { dark: warningDark, light: '#def' },
  error: { main: '#123456' },
  success: { main: '#654321' }
});

let monacoValue: any = null;
let themePalette = createPalette();

vi.mock('@monaco-editor/react', () => ({
  Editor: (props: any) => {
    capturedProps.current = props;
    return <div>editor</div>;
  },
  useMonaco: () => monacoValue
}));

vi.mock('@mui/material', () => ({
  useTheme: () => ({ palette: themePalette })
}));

import ThemedEditor from './ThemedEditor';

describe('ThemedEditor', () => {
  beforeEach(() => {
    themePalette = createPalette();
    monacoValue = null;
    vi.clearAllMocks();
  });

  it('defines custom monaco themes and merges editor options', () => {
    monacoValue = { editor: { defineTheme: mockDefineTheme, setTheme: mockSetTheme } };
    render(<ThemedEditor id="the-editor" options={{ readOnly: true }} beforeMount={vi.fn()} value="x" />);

    const fakeMonaco = {
      editor: { defineTheme: mockDefineTheme },
      languages: { register: mockRegisterLanguage }
    };
    capturedProps.current.beforeMount(fakeMonaco);

    expect(mockDefineTheme).toHaveBeenCalledWith(
      'howler',
      expect.objectContaining({
        base: 'vs',
        colors: expect.objectContaining({ 'editor.background': '#FFFFFF', 'editor.foreground': '#202020' })
      })
    );
    expect(mockRegisterLanguage).toHaveBeenCalledWith({ id: 'lucene' });
    expect(capturedProps.current.wrapperProps).toEqual({ id: 'the-editor' });
    expect(capturedProps.current.options).toMatchObject({ readOnly: true, automaticLayout: true });
    expect(mockSetTheme).toHaveBeenCalledWith('howler');
  });

  it('converts RGB palette colors to Monaco token colors', () => {
    themePalette = createPalette('light', '#fff', '#0055aa', '#202020', 'RGB(126, 95, 0)');
    monacoValue = { editor: { defineTheme: mockDefineTheme, setTheme: mockSetTheme } };
    render(<ThemedEditor value="x" />);

    capturedProps.current.beforeMount({
      editor: { defineTheme: mockDefineTheme },
      languages: { register: mockRegisterLanguage }
    });

    expect(mockDefineTheme).toHaveBeenCalledWith(
      'howler',
      expect.objectContaining({
        rules: expect.arrayContaining([expect.objectContaining({ token: 'handlebars', foreground: '7E5F00' })])
      })
    );
  });

  it('uses and updates colors from the active app theme', () => {
    themePalette = createPalette('dark', '#002B36');
    monacoValue = { editor: { defineTheme: mockDefineTheme, setTheme: mockSetTheme } };
    const { rerender } = render(<ThemedEditor value="x" />);

    expect(capturedProps.current.theme).toBe('howler');
    expect(mockDefineTheme).toHaveBeenLastCalledWith(
      'howler',
      expect.objectContaining({
        base: 'vs-dark',
        colors: expect.objectContaining({
          'editor.background': '#002B36',
          'editor.foreground': '#EEE8D5',
          'editor.selectionBackground': '#0A141E33'
        })
      })
    );
    expect(mockSetTheme).toHaveBeenCalledWith('howler');

    themePalette = createPalette('dark', '#101010', '#cc5500', '#f0f0f0');
    rerender(<ThemedEditor value="y" />);

    expect(mockDefineTheme).toHaveBeenLastCalledWith(
      'howler',
      expect.objectContaining({
        base: 'vs-dark',
        colors: expect.objectContaining({
          'editor.background': '#101010',
          'editor.foreground': '#F0F0F0',
          'editorCursor.foreground': '#CC5500'
        })
      })
    );
  });
});
