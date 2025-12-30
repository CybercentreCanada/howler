import { http, HttpResponse } from 'msw';
import { createMockAction } from './utils';

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
    items: [
      {
        howler: {
          id: 'howler.id'
        }
      }
    ],
    total: 1,
    rows: 1
  },
  '/api/v1/search/view': {
    items: [
      {
        owner: 'user',
        settings: {
          advance_on_triage: false
        },
        view_id: 'searched_view_id',
        query: 'howler.id:searched',
        sort: 'event.created desc',
        title: 'Searched View',
        type: 'personal',
        span: 'date.range.1.month'
      }
    ],
    total: 1,
    rows: 1
  },
  '/api/v1/view/new_view_id': {
    owner: 'user',
    settings: {
      advance_on_triage: false
    },
    view_id: 'new_view_id',
    query: 'howler.id:new',
    sort: 'event.created desc',
    title: 'New View',
    type: 'personal',
    span: 'date.range.1.month'
  },
  '/api/v1/view/:view_id/favourite': { success: true },
  '/api/v1/search/action': {
    items: [createMockAction()],
    total: 1,
    rows: 1
  }
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
  )
];

export { handlers };
