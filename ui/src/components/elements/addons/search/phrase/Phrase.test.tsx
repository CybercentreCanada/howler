/// <reference types="vitest" />
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockExecCommand = vi.hoisted(() => vi.fn());
const mockParse = vi.hoisted(() => vi.fn());
const mockSuggest = vi.hoisted(() => vi.fn());

vi.mock('@mui/material', async importOriginal => {
  const React = await import('react');
  return {
    ClickAwayListener: ({ children, onClickAway }: any) => <div onClick={onClickAway}>{children}</div>,
    InputAdornment: ({ children }: any) => <div>{children}</div>,
    ListItemText: ({ children }: any) => <div>{children}</div>,
    MenuItem: ({ children, onClick }: any) => <button onClick={onClick}>{children}</button>,
    MenuList: ({ children, ref, onKeyDown }: any) => <div ref={ref} tabIndex={0} onKeyDown={onKeyDown}>{children}</div>,
    Paper: ({ children }: any) => <div>{children}</div>,
    Popper: ({ children, open }: any) => (open ? <div>{children}</div> : null),
    TextField: React.forwardRef(({ value, onChange, onKeyDown, InputProps, label }: any, ref: any) => (
      <div ref={ref}>
        <label>{label}</label>
        <input
          aria-label={label ?? 'phrase'}
          value={value}
          onChange={onChange}
          onKeyDown={onKeyDown}
          onSelect={InputProps?.onSelectCapture}
        />
        {InputProps?.startAdornment}
        {InputProps?.endAdornment}
      </div>
    ))
  };
});

vi.mock('@tui/core', () => ({
  parseEvent: (event: any) => ({
    isEnter: event.key === 'Enter',
    isCtrl: !!event.ctrlKey,
    isSpace: event.key === ' ',
    isEscape: event.key === 'Escape',
    isArrowDown: event.key === 'ArrowDown'
  })
}));

vi.mock('./word/WordLexer', () => ({
  default: class {
    parse(value: string, cursor: number) {
      return mockParse(value, cursor);
    }
  }
}));

vi.mock('./word/WordSuggester', () => ({
  default: class {
    constructor(_suggestions: string[]) {}
    suggest(analysis: any) {
      return mockSuggest(analysis);
    }
  }
}));

import Phrase from './Phrase';

describe('Phrase', () => {
  beforeEach(() => {
    mockParse.mockReset().mockReturnValue({
      suggest: { token: { startIndex: 0, endIndex: 2 } },
      tokens: ['abc']
    });
    mockSuggest.mockReset().mockReturnValue(['alpha']);
    document.execCommand = mockExecCommand as any;
  });

  it('updates the phrase and supports ctrl-space, enter, click, and escape suggestion flows', () => {
    const onChange = vi.fn();
    const onKeyDown = vi.fn();

    render(<Phrase label="phrase" value="abc" suggestions={['alpha', 'beta']} onChange={onChange} onKeyDown={onKeyDown} />);

    const input = screen.getByLabelText('phrase');
    Object.defineProperty(input, 'selectionStart', { configurable: true, value: 1 });
    (input as HTMLInputElement).setSelectionRange = vi.fn();
    (input as HTMLInputElement).focus = vi.fn();

    fireEvent.change(input, { target: { value: 'next' } });
    expect(onChange).toHaveBeenCalledWith('next');

    fireEvent.keyDown(input, { key: ' ', ctrlKey: true });
    expect(screen.getByText('alpha')).toBeInTheDocument();

    fireEvent.keyDown(input, { key: 'Enter' });
    expect(mockExecCommand).toHaveBeenCalledWith('insertText', false, 'alpha');

    fireEvent.keyDown(input, { key: 'Escape' });
    fireEvent.select(input);
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    fireEvent.keyDown(input, { key: 'Tab' });
    expect(onKeyDown).toHaveBeenCalled();

    fireEvent.click(screen.getByText('alpha'));
    expect(mockExecCommand).toHaveBeenCalledTimes(2);
  });
});
