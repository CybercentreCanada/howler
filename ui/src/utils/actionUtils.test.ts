/// <reference types="vitest" />
import type { ActionOperation, ActionOperationStep } from 'models/ActionTypes';
import { describe, expect, it } from 'vitest';
import { checkArgsAreFilled, getArgsByContext, getOptionsByContext, operationReady } from './actionUtils';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const makeStep = (
  args: ActionOperationStep['args'],
  options: ActionOperationStep['options'] = {}
): ActionOperationStep =>
  ({
    args,
    options,
    validation: {}
  }) as ActionOperationStep;

const makeAction = (steps: ActionOperationStep[]): ActionOperation =>
  ({
    id: 'test-action',
    title: 'Test Action',
    i18nKey: 'test.action',
    description: { short: '', long: '' },
    roles: [],
    steps,
    triggers: []
  }) as ActionOperation;

// ---------------------------------------------------------------------------
// checkArgsAreFilled
// ---------------------------------------------------------------------------

describe('checkArgsAreFilled', () => {
  it('returns false when values is empty/falsy', () => {
    const step = makeStep({ status: [] });
    expect(checkArgsAreFilled(step, '')).toBe(false);
  });

  it('returns true when all required args are present and truthy', () => {
    const step = makeStep({ status: [] });
    expect(checkArgsAreFilled(step, JSON.stringify({ status: 'open' }))).toBe(true);
  });

  it('returns false when a required arg is missing from values', () => {
    const step = makeStep({ status: [], assignment: [] });
    expect(checkArgsAreFilled(step, JSON.stringify({ status: 'open' }))).toBe(false);
  });

  it('returns false when a required arg is present but falsy (empty string)', () => {
    const step = makeStep({ status: [] });
    expect(checkArgsAreFilled(step, JSON.stringify({ status: '' }))).toBe(false);
  });

  it('returns true when there are no required args', () => {
    const step = makeStep({});
    expect(checkArgsAreFilled(step, JSON.stringify({}))).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// getOptionsByContext
// ---------------------------------------------------------------------------

describe('getOptionsByContext', () => {
  it('returns an empty array when the arg is not in options', () => {
    const options = {};
    expect(getOptionsByContext(options, 'status', '{}')).toEqual([]);
  });

  it('returns the full list when the arg maps to a plain array', () => {
    const options = { status: ['open', 'in-progress', 'resolved'] };
    expect(getOptionsByContext(options, 'status', '{}')).toEqual(['open', 'in-progress', 'resolved']);
  });

  it('returns options matching the current context when arg has conditional options', () => {
    const options = {
      assessment: {
        'status:open': ['false_positive', 'legitimate'],
        'status:resolved': ['correct']
      }
    };
    const context = JSON.stringify({ status: 'open' });
    expect(getOptionsByContext(options, 'assessment', context)).toEqual(['false_positive', 'legitimate']);
  });

  it('returns an empty array when context does not match any conditional key', () => {
    const options = {
      assessment: {
        'status:open': ['false_positive']
      }
    };
    const context = JSON.stringify({ status: 'resolved' });
    expect(getOptionsByContext(options, 'assessment', context)).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// getArgsByContext
// ---------------------------------------------------------------------------

describe('getArgsByContext', () => {
  it('always returns an arg with an empty conditions array', () => {
    const args = { status: [] };
    expect(getArgsByContext(args, '{}')).toContain('status');
  });

  it('includes an arg whose condition matches the current context', () => {
    const args = { assessment: ['status:open'] };
    const values = JSON.stringify({ status: 'open' });
    expect(getArgsByContext(args, values)).toContain('assessment');
  });

  it('excludes an arg whose condition does not match the current context', () => {
    const args = { assessment: ['status:open'] };
    const values = JSON.stringify({ status: 'resolved' });
    expect(getArgsByContext(args, values)).not.toContain('assessment');
  });

  it('includes an arg when any one of multiple conditions matches (OR logic)', () => {
    const args = { rationale: ['status:open', 'status:in-progress'] };
    const values = JSON.stringify({ status: 'in-progress' });
    expect(getArgsByContext(args, values)).toContain('rationale');
  });

  it('returns an empty array when no args match', () => {
    const args = { assessment: ['status:open'] };
    const values = JSON.stringify({ status: 'resolved' });
    expect(getArgsByContext(args, values)).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// operationReady
// ---------------------------------------------------------------------------

describe('operationReady', () => {
  it('returns false when data is null/falsy', () => {
    const action = makeAction([makeStep({ status: [] })]);
    expect(operationReady(null, action)).toBe(false);
  });

  it('returns falsy when action is falsy', () => {
    expect(operationReady(JSON.stringify({ status: 'open' }), null)).toBeFalsy();
  });

  it('returns true when all unconditional args are present', () => {
    const action = makeAction([makeStep({ status: [] })]);
    const data = JSON.stringify({ status: 'open' });
    expect(operationReady(data, action)).toBe(true);
  });

  it('returns false when a required unconditional arg is missing', () => {
    const action = makeAction([makeStep({ status: [], assessment: [] })]);
    const data = JSON.stringify({ status: 'open' });
    expect(operationReady(data, action)).toBe(false);
  });

  it('ignores conditional args that do not apply in the current context', () => {
    // assessment only required when status=open; here status=resolved so assessment is not required
    const action = makeAction([makeStep({ status: [], assessment: ['status:open'] })]);
    const data = JSON.stringify({ status: 'resolved' });
    expect(operationReady(data, action)).toBe(true);
  });

  it('merges args across multiple steps', () => {
    const step1 = makeStep({ status: [] });
    const step2 = makeStep({ assignment: [] });
    const action = makeAction([step1, step2]);
    const data = JSON.stringify({ status: 'open', assignment: 'alice' });
    expect(operationReady(data, action)).toBe(true);
  });
});
