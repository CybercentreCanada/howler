import { describe, expect, it, vi } from 'vitest';

vi.mock('api/v2/case', () => ({ sentinel: 'case' }));
vi.mock('api/v2/fuzzy', () => ({ sentinel: 'fuzzy' }));
vi.mock('api/v2/search', () => ({ sentinel: 'search' }));

import { case as caseApi, fuzzy, search, uri } from './index';

describe('v2 API', () => {
  it('builds the v2 root URI and re-exports v2 modules', () => {
    expect(uri()).toBe('/api/v2');
    expect(caseApi).toEqual({ sentinel: 'case' });
    expect(fuzzy).toEqual({ sentinel: 'fuzzy' });
    expect(search).toEqual({ sentinel: 'search' });
  });
});
