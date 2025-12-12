import type { Action } from 'models/entities/generated/Action';
import type { Analytic } from 'models/entities/generated/Analytic';
import type { Hit } from 'models/entities/generated/Hit';
import type { Template } from 'models/entities/generated/Template';
import type { View } from 'models/entities/generated/View';

type RecursivePartial<T> = {
  [P in keyof T]?: T[P] extends (infer U)[]
    ? RecursivePartial<U>[]
    : T[P] extends object | undefined
      ? RecursivePartial<T[P]>
      : T[P];
};

// Mock data factories
export const createMockHit = (overrides?: RecursivePartial<Hit>): Hit =>
  ({
    howler: {
      id: 'test-hit-1',
      analytic: 'test-analytic',
      detection: 'Test Detection',
      status: 'open',
      assessment: null,
      outline: { indicators: ['a', 'b', 'c'] },
      ...overrides?.howler
    },
    event: {
      id: 'event-123',
      ...overrides?.event
    }
  }) as Hit;

export const createMockAnalytic = (overrides?: Partial<Analytic>): Analytic => ({
  analytic_id: 'test-analytic-id',
  name: 'test-analytic',
  triage_settings: {
    valid_assessments: ['legitimate', 'false_positive'],
    skip_rationale: false,
    ...overrides?.triage_settings
  },
  ...overrides
});

export const createMockTemplate = (overrides?: Partial<Template>): Template => ({
  keys: ['howler.detection', 'event.id'],
  ...overrides
});

export const createMockAction = (overrides?: Partial<Action>): Action => ({
  action_id: 'action-1',
  name: 'Test Action',
  operations: [
    {
      data_json: '{}',
      operation_id: 'transition'
    }
  ],
  ...overrides
});

export const createMockView = (overrides?: Partial<View>): View => ({
  view_id: 'test-view-id',
  title: 'Test View',
  query: 'howler.status:open',
  sort: 'event.created desc',
  span: 'date.range.1.month',
  type: 'personal',
  owner: 'testuser',
  settings: {
    advance_on_triage: false
  },
  ...overrides
});
