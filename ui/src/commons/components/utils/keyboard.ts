import { type KeyboardEvent } from 'react';

export const ENTER = 'Enter';
export const ESCAPE = 'Escape';
export const ARROW_LEFT = 'ArrowLeft';
export const ARROW_UP = 'ArrowUp';
export const ARROW_RIGHT = 'ArrowRight';
export const ARROW_DOWN = 'ArrowDown';
export const BACKSPACE = 'Backspace';
export const SPACE = ' ';

export function is(key: string, check: string) {
  return key === check;
}

export function isArrowUp(key: string) {
  return is(key, ARROW_UP);
}

export function isArrowDown(key: string) {
  return is(key, ARROW_DOWN);
}

export function isArrowLeft(key: string) {
  return is(key, ARROW_LEFT);
}

export function isArrowRight(key: string) {
  return is(key, ARROW_RIGHT);
}

export function isEscape(key: string) {
  return is(key, ESCAPE);
}

export function isEnter(key: string) {
  return is(key, ENTER);
}

export function isBackspace(key: string) {
  return is(key, BACKSPACE);
}

export function isSpace(key: string) {
  return is(key, SPACE);
}

export function parseEvent(event: KeyboardEvent<HTMLElement>) {
  return {
    key: event.key,
    isCtrl: event.ctrlKey,
    isEnter: isEnter(event.key),
    isSpace: isSpace(event.key),
    isBackspace: isBackspace(event.key),
    isEscape: isEscape(event.key),
    isArrowLeft: isArrowLeft(event.key),
    isArrowRight: isArrowRight(event.key),
    isArrowUp: isArrowUp(event.key),
    isArrowDown: isArrowDown(event.key)
  };
}
