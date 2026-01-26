import { http, HttpResponse } from 'msw';
import { createMockAction, createMockAnalytic, createMockHit, createMockView } from './utils';

export const MOCK_RESPONSES: { [path: string]: any } = {
  '/api/v1/view/example_view_id': {
    owner: 'user',
    settings: {
      advance_on_triage: false
    },
    view_id: 'example_view_id',
    query: 'howler.id:*',
    sort: 'event.created desc',
    title: 'Example View',
    type: 'personal',
    span: 'date.range.1.month'
  },
  '/api/v1/search/hit': {
    items: [createMockHit({ howler: { id: 'howler.id' } })],
    total: 1,
    rows: 1
  },
  '/api/v1/search/view': {
    items: [createMockView({ view_id: 'searched_view_id', title: 'Searched View' })],
    total: 1,
    rows: 1
  },
  '/api/v1/view/new_view_id': createMockView({ view_id: 'new_view_id' }),
  '/api/v1/view/:view_id/favourite': { success: true },
  '/api/v1/search/action': {
    items: [createMockAction()],
    total: 1,
    rows: 1
  },
  '/api/v1/analytic': [createMockAnalytic()]
};

const handlers = [
  ...Object.entries(MOCK_RESPONSES).map(([path, data]) =>
    http.all(path, async () => HttpResponse.json({ api_response: data }))
  ),
  http.post('/api/v1/view', async () =>
    HttpResponse.json(
      {
        api_response: {
          owner: 'user',
          settings: {
            advance_on_triage: false
          },
          view_id: 'example_created_view',
          query: 'howler.id:*',
          sort: 'event.created desc',
          title: 'Example View',
          type: 'personal',
          span: 'date.range.1.month'
        }
      },
      { status: 201 }
    )
  ),
  http.delete('/api/v1/view/:view_id', async () =>
    HttpResponse.json(
      {
        api_response: {
          success: true
        }
      },
      { status: 204 }
    )
  ),
  http.get('/api/v1/view', async () =>
    HttpResponse.json({
      api_response: [
        {
          owner: 'user',
          settings: {
            advance_on_triage: false
          },
          view_id: 'example_view_id',
          query: 'howler.id:*',
          sort: 'event.created desc',
          title: 'Example View',
          type: 'personal',
          span: 'date.range.1.month'
        },
        {
          owner: 'user',
          settings: {
            advance_on_triage: true
          },
          view_id: 'another_view_id',
          query: 'howler.status:open',
          sort: 'event.created asc',
          title: 'Another View',
          type: 'global',
          span: 'date.range.1.week'
        }
      ]
    })
  ),
  http.post('/api/v1/search/facet/hit', async ({ request }) => {
    const payload: any = await request.json();

    let facetResponse = Object.fromEntries(payload.fields.map(field => [field, { 'facet 1': 1, 'facet 2': 2 }]));
    if (payload.filters?.[0]?.includes('analytic')) {
      facetResponse = Object.fromEntries(payload.fields.map(field => [field, { 'Analytic 1': 1, 'Analytic 2': 2 }]));
    } else if (payload.query.includes('test-user')) {
      facetResponse = Object.fromEntries(
        payload.fields.map(field => [field, { 'Assignment 1': 1, 'Assignment 2': 2 }])
      );
    }

    return HttpResponse.json({
      api_response: facetResponse
    });
  })
];

export { handlers };
