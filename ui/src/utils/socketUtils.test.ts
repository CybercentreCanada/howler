import { describe, expect, it } from 'vitest';
import { isCaseUpdate, isHitUpdate, isViewersUpdate } from './socketUtils';

describe('isHitUpdate', () => {
  it('returns true when data has version and hit', () => {
    const data = { version: '1', hit: { howler: { id: 'h1' } }, type: 'hits', error: false, message: '', status: 200 };
    expect(isHitUpdate(data)).toBeTruthy();
  });

  it('returns false when hit is missing', () => {
    const data = { version: '1', type: 'hits', error: false, message: '', status: 200 };
    expect(isHitUpdate(data)).toBeFalsy();
  });

  it('returns false when version is missing', () => {
    const data = { hit: { howler: { id: 'h1' } }, type: 'hits', error: false, message: '', status: 200 };
    expect(isHitUpdate(data)).toBeFalsy();
  });
});

describe('isCaseUpdate', () => {
  it('returns true when type is cases and case is present', () => {
    const data = { type: 'cases', case: { case_id: 'c1' }, error: false, message: '', status: 200 };
    expect(isCaseUpdate(data)).toBeTruthy();
  });

  it('returns false when type is not cases', () => {
    const data = { type: 'hits', case: { case_id: 'c1' }, error: false, message: '', status: 200 };
    expect(isCaseUpdate(data)).toBeFalsy();
  });

  it('returns false when case is missing', () => {
    const data = { type: 'cases', error: false, message: '', status: 200 };
    expect(isCaseUpdate(data)).toBeFalsy();
  });

  it('returns false when case is null', () => {
    const data = { type: 'cases', case: null, error: false, message: '', status: 200 };
    expect(isCaseUpdate(data)).toBeFalsy();
  });
});

describe('isViewersUpdate', () => {
  it('returns true when type is viewers_update with id and viewers', () => {
    const data = {
      type: 'viewers_update',
      id: 'entity-1',
      viewers: ['alice', 'bob'],
      error: false,
      message: '',
      status: 200
    };
    expect(isViewersUpdate(data)).toBeTruthy();
  });

  it('returns false when type is wrong', () => {
    const data = { type: 'cases', id: 'entity-1', viewers: ['alice'], error: false, message: '', status: 200 };
    expect(isViewersUpdate(data)).toBeFalsy();
  });

  it('returns false when viewers is missing', () => {
    const data = { type: 'viewers_update', id: 'entity-1', error: false, message: '', status: 200 };
    expect(isViewersUpdate(data)).toBeFalsy();
  });

  it('returns false when id is missing', () => {
    const data = { type: 'viewers_update', viewers: ['alice'], error: false, message: '', status: 200 };
    expect(isViewersUpdate(data)).toBeFalsy();
  });
});
