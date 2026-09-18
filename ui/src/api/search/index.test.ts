import { describe, expect, it, vi } from 'vitest';

const mockJoinUri = vi.hoisted(() => vi.fn(() => '/api/v1/search'));

vi.mock('api', () => ({
  joinUri: mockJoinUri,
  uri: () => '/api/v1'
}));

vi.mock('api/search/action', () => ({ sentinel: 'action' }));
vi.mock('api/search/analytic', () => ({ sentinel: 'analytic' }));
vi.mock('api/search/case', () => ({ sentinel: 'case' }));
vi.mock('api/search/count', () => ({ sentinel: 'count' }));
vi.mock('api/search/dossier', () => ({ sentinel: 'dossier' }));
vi.mock('api/search/facet', () => ({ sentinel: 'facet' }));
vi.mock('api/search/fields', () => ({ sentinel: 'fields' }));
vi.mock('api/search/grouped', () => ({ sentinel: 'grouped' }));
vi.mock('api/search/histogram', () => ({ sentinel: 'histogram' }));
vi.mock('api/search/hit', () => ({ sentinel: 'hit' }));
vi.mock('api/search/overview', () => ({ sentinel: 'overview' }));
vi.mock('api/search/template', () => ({ sentinel: 'template' }));
vi.mock('api/search/user', () => ({ sentinel: 'user' }));
vi.mock('api/search/view', () => ({ sentinel: 'view' }));

import { action, analytic, case as caseApi, count, dossier, facet, fields, grouped, histogram, hit, overview, template, uri, user, view } from './index';

describe('search API', () => {
  it('builds the search URI and re-exports nested search modules', () => {
    expect(uri()).toBe('/api/v1/search');
    expect(mockJoinUri).toHaveBeenCalledWith('/api/v1', 'search');
    expect(action).toEqual({ sentinel: 'action' });
    expect(analytic).toEqual({ sentinel: 'analytic' });
    expect(caseApi).toEqual({ sentinel: 'case' });
    expect(count).toEqual({ sentinel: 'count' });
    expect(dossier).toEqual({ sentinel: 'dossier' });
    expect(facet).toEqual({ sentinel: 'facet' });
    expect(fields).toEqual({ sentinel: 'fields' });
    expect(grouped).toEqual({ sentinel: 'grouped' });
    expect(histogram).toEqual({ sentinel: 'histogram' });
    expect(hit).toEqual({ sentinel: 'hit' });
    expect(overview).toEqual({ sentinel: 'overview' });
    expect(template).toEqual({ sentinel: 'template' });
    expect(user).toEqual({ sentinel: 'user' });
    expect(view).toEqual({ sentinel: 'view' });
  });
});
