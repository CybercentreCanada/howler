/// <reference types="vitest" />
import { afterEach, describe, expect, it } from 'vitest';
import getXSRFCookie from './xsrf';

describe('getXSRFCookie', () => {
  const originalDescriptor = Object.getOwnPropertyDescriptor(document, 'cookie');

  const setCookie = (value: string) => {
    Object.defineProperty(document, 'cookie', {
      get: () => value,
      configurable: true
    });
  };

  afterEach(() => {
    if (originalDescriptor) {
      Object.defineProperty(document, 'cookie', originalDescriptor);
    }
  });

  it('returns null when document.cookie is empty', () => {
    setCookie('');
    expect(getXSRFCookie()).toBeNull();
  });

  it('returns null when XSRF-TOKEN is not among the cookies', () => {
    setCookie('session=abc; theme=dark');
    expect(getXSRFCookie()).toBeNull();
  });

  it('returns the XSRF-TOKEN value when it is the only cookie', () => {
    setCookie('XSRF-TOKEN=my-token');
    expect(getXSRFCookie()).toBe('my-token');
  });

  it('returns the XSRF-TOKEN value when it appears among other cookies', () => {
    setCookie('session=abc; XSRF-TOKEN=csrf-value; theme=dark');
    expect(getXSRFCookie()).toBe('csrf-value');
  });

  it('returns the XSRF-TOKEN value when it appears first', () => {
    setCookie('XSRF-TOKEN=first-token; session=abc');
    expect(getXSRFCookie()).toBe('first-token');
  });

  it('returns the XSRF-TOKEN value when it appears last', () => {
    setCookie('session=abc; XSRF-TOKEN=last-token');
    expect(getXSRFCookie()).toBe('last-token');
  });
});
