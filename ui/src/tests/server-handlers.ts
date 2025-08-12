import { http, HttpResponse } from 'msw';

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
  }
};

const handlers = [
  ...Object.entries(MOCK_RESPONSES).map(([path, data]) =>
    http.all(path, async () => HttpResponse.json({ api_response: data }))
  )
];

export { handlers };
