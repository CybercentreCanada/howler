import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHdelete = vi.hoisted(() => vi.fn());
const mockHpost = vi.hoisted(() => vi.fn());
const mockHput = vi.hoisted(() => vi.fn());
const mockJoinAllUri = vi.hoisted(() => vi.fn((...parts: string[]) => parts.join('/').replace(/\/+/g, '/')));

vi.mock('api', () => ({
  hdelete: mockHdelete,
  hpost: mockHpost,
  hput: mockHput,
  joinAllUri: mockJoinAllUri
}));

vi.mock('api/v2/case', () => ({
  uri: (caseId: string) => `/api/v2/case/${caseId}`
}));

import { del, post, put, uri } from './rules';

describe('v2 case rules API', () => {
  beforeEach(() => {
    mockHdelete.mockReset();
    mockHpost.mockReset();
    mockHput.mockReset();
    mockJoinAllUri.mockClear();
  });

  it('builds collection and detail rule URIs and calls each HTTP method', async () => {
    expect(uri('case-1')).toBe('/api/v2/case/case-1/rules');
    expect(uri('case-1', 'rule-1')).toBe('/api/v2/case/case-1/rules/rule-1');

    await post('case-1', { name: 'rule' } as any);
    await put('case-1', 'rule-1', { name: 'updated' } as any);
    await del('case-1', 'rule-1');

    expect(mockHpost).toHaveBeenCalledWith('/api/v2/case/case-1/rules', { name: 'rule' });
    expect(mockHput).toHaveBeenCalledWith('/api/v2/case/case-1/rules/rule-1', { name: 'updated' });
    expect(mockHdelete).toHaveBeenCalledWith('/api/v2/case/case-1/rules/rule-1');
  });
});
