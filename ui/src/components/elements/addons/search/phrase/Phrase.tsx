import {
  ClickAwayListener,
  InputAdornment,
  ListItemText,
  MenuItem,
  MenuList,
  Paper,
  Popper,
  TextField,
  type TextFieldProps
} from '@mui/material';
import { parseEvent } from 'commons/components/utils/keyboard';
import { type ChangeEvent, type KeyboardEvent, type ReactElement, useEffect, useRef, useState } from 'react';
import type { PhraseAnalysis, PhraseSuggester } from '.';
import type PhraseLexer from './PhraseLexer';
import WordLexer from './word/WordLexer';
import WordSuggestor from './word/WordSuggester';

export type PhraseProps = Omit<TextFieldProps, 'onChange' | 'onKeyDown' | 'variant'> & {
  value: string;
  variant?: 'filled' | 'outlined' | 'standard';
  suggestions?: string[];
  lexer?: PhraseLexer;
  suggester?: PhraseSuggester;
  debug?: boolean;
  startAdornment?: ReactElement | ReactElement[];
  endAdornment?: ReactElement | ReactElement[];
  onChange: (phrase: string) => void;
  onKeyDown?: (event: ReturnType<typeof parseEvent>) => void;
};

const Phrase = ({
  value = '',
  variant = 'outlined',
  suggestions = [],
  lexer,
  suggester,
  debug,
  startAdornment,
  endAdornment,
  onChange,
  onKeyDown,
  ...props
}: PhraseProps) => {
  const containerRef = useRef<HTMLDivElement>();
  const inputRef = useRef<HTMLDivElement>();
  const menuRef = useRef<HTMLUListElement>();
  const lexerRef = useRef<PhraseLexer>(lexer || new WordLexer());
  const analysisRef = useRef<PhraseAnalysis>();
  const suggesterRef = useRef<PhraseSuggester>(suggester || new WordSuggestor(suggestions));
  const [optionsOpen, setOptionsOpen] = useState<boolean>(false);
  const [options, setOptions] = useState<string[]>(suggestions);

  useEffect(() => {
    suggesterRef.current = suggester || new WordSuggestor(suggestions);
  }, [suggester, suggestions]);

  const lex = (inputValue: string, offset = 0): PhraseAnalysis => {
    let cursor = inputRef.current.querySelector('input').selectionStart + offset;
    cursor = cursor < 0 ? 0 : cursor > inputValue.length ? inputValue.length : cursor;
    analysisRef.current = lexerRef.current.parse(inputValue, cursor);
    return analysisRef.current;
  };

  const onWordClick = (word: string) => {
    const { suggest } = analysisRef.current;

    const inputEl = inputRef.current.querySelector('input');

    // NOTE: this is the only thing that works well with UNDO/REDO
    // NOTE: the 'deprecated' insertText has no proper replacement to support this yet.
    inputEl.focus();
    inputEl.setSelectionRange(suggest.token.startIndex, suggest.token.endIndex + 1);
    document.execCommand('insertText', false, word);
    // NOTE: setRangeText does not work with UNDO/REDO [CTRL+Z|CTRL+SHIFT+Z]
    // inputEl.setRangeText(word, current.startIndex, current.endIndex + 1, 'end');

    setOptionsOpen(false);
  };

  const _suggest = (inputValue: string, offset = 0) => {
    const _suggestions = suggesterRef.current.suggest(lex(inputValue, offset));
    setOptions(_suggestions?.length > 0 ? _suggestions : [...suggestions]);
  };

  const _onChange = (event: ChangeEvent<HTMLInputElement>) => {
    onChange(event.target.value);
  };

  const _onInputKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    const parsedEvent = parseEvent(event);
    const { isEnter, isCtrl, isSpace, isEscape, isArrowDown } = parsedEvent;
    if (isArrowDown) {
      event.preventDefault(); // prevent native scroll.
      menuRef.current.focus(); // ensure suggestion menu gets focus.
    } else if (isCtrl && isSpace) {
      setOptionsOpen(true);
      _suggest(value);
    } else if (isEscape) {
      setOptionsOpen(!optionsOpen);
    }
    if (isEnter && optionsOpen && options.length === 1) {
      onWordClick(options[0]);
      event.preventDefault();
    } else if (onKeyDown) {
      onKeyDown(parsedEvent);
    }
  };

  const _onSelectCapture = event => {
    if (optionsOpen) {
      _suggest(event.target.value);
    }
  };

  const _onMenuKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    const { isEscape } = parseEvent(event);
    if (isEscape) {
      inputRef.current.focus();
      setOptionsOpen(false);
    }
  };

  return (
    <ClickAwayListener onClickAway={() => setOptionsOpen(false)}>
      <div ref={containerRef} style={{ position: 'relative' }}>
        <TextField
          ref={inputRef}
          {...props}
          fullWidth
          autoComplete="off"
          value={value}
          variant={variant}
          onChange={_onChange}
          onKeyDown={_onInputKeyDown}
          InputProps={{
            ...props.InputProps,
            onSelectCapture: _onSelectCapture,
            startAdornment: startAdornment && <InputAdornment position="start">{startAdornment}</InputAdornment>,
            endAdornment: endAdornment && <InputAdornment position="end">{endAdornment}</InputAdornment>
          }}
        />
        <Popper
          anchorEl={containerRef.current}
          style={{ width: '100%', zIndex: 100 }}
          open={optionsOpen && (options.length > 0 || (debug && analysisRef.current?.tokens.length > 0))}
          disablePortal
        >
          <Paper
            elevation={2}
            sx={{ maxHeight: 200, overflow: 'auto', borderTopRightRadius: 0, borderTopLeftRadius: 0 }}
          >
            <MenuList
              ref={menuRef}
              onKeyDown={_onMenuKeyDown}
              sx={{
                '&:focus': {
                  outline: 'none'
                }
              }}
            >
              {options?.map(o => (
                <MenuItem key={o} onClick={() => onWordClick(o)}>
                  <ListItemText>{o}</ListItemText>
                </MenuItem>
              ))}
            </MenuList>
          </Paper>
        </Popper>
      </div>
    </ClickAwayListener>
  );
};

export default Phrase;
