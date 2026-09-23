/// <reference types="vitest" />
import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const mockDefineTheme = vi.hoisted(() => vi.fn());
const mockRegisterLanguage = vi.hoisted(() => vi.fn());
const mockSetTheme = vi.hoisted(() => vi.fn());
const capturedProps = vi.hoisted(() => ({ current: null as any }));

let themeMode: 'light' | 'dark' = 'light';
let monacoValue: any = null;

vi.mock('@monaco-editor/react', () => ({
  Editor: (props: any) => {
    capturedProps.current = props;
    return <div>editor</div>;
  },
  useMonaco: () => monacoValue
}));

vi.mock('@mui/material', () => ({
  useTheme: () => ({ palette: { mode: themeMode, background: { paper: themeMode === 'light' ? '#fff' : '#111' } } })
}));

vi.mock('@tui/core', () => ({
  useAppTheme: () => ({ current: 'default', optionsOverride: { dense: true } }),
  useAppThemeBuilder: () => () => ({
    lightTheme: {
      palette: {
        background: { paper: '#fff' },
        warning: { dark: '#abc', light: '#def' },
        error: { main: '#123456' },
        success: { main: '#654321' }
      }
    },
    darkTheme: {
      palette: {
        background: { paper: '#111' },
        warning: { dark: '#aaa', light: '#bbb' },
        error: { main: '#222222' },
        success: { main: '#333333' }
      }
    }
  })
}));

import ThemedEditor from './ThemedEditor';

describe('ThemedEditor', () => {
  it('defines custom monaco themes and merges editor options', () => {
    monacoValue = { editor: { setTheme: mockSetTheme } };
    render(<ThemedEditor id="the-editor" options={{ readOnly: true }} beforeMount={vi.fn()} value="x" />);

    const fakeMonaco = {
      editor: { defineTheme: mockDefineTheme },
      languages: { register: mockRegisterLanguage }
    };
    capturedProps.current.beforeMount(fakeMonaco);

    expect(mockDefineTheme).toHaveBeenCalledWith(
      'howler',
      expect.objectContaining({ colors: { 'editor.background': '#ffffff' } })
    );
    expect(mockDefineTheme).toHaveBeenCalledWith(
      'howler-dark',
      expect.objectContaining({ colors: { 'editor.background': '#111111' } })
    );
    expect(mockRegisterLanguage).toHaveBeenCalledWith({ id: 'lucene' });
    expect(capturedProps.current.wrapperProps).toEqual({ id: 'the-editor' });
    expect(capturedProps.current.options).toMatchObject({ readOnly: true, automaticLayout: true });
    expect(mockSetTheme).toHaveBeenCalledWith('howler');
  });

  it('switches to the dark theme when the mui theme changes', () => {
    themeMode = 'dark';
    monacoValue = { editor: { setTheme: mockSetTheme } };
    render(<ThemedEditor value="x" />);
    expect(capturedProps.current.theme).toBe('howler-dark');
    expect(mockSetTheme).toHaveBeenCalledWith('howler-dark');
  });
});
