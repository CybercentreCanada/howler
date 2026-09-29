/// <reference types="vitest" />
import { describe, expect, it } from 'vitest';
import { missingContext } from './contextUtils';

describe('missingContext', () => {
  it('throws a provider-specific error', () => {
    expect(() => missingContext('DemoContext')).toThrow('DemoContext must be used within its provider.');
  });
});
