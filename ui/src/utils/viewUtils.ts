import type { View } from 'models/entities/generated/View';

export const buildViewUrl = (view: View) => {
  const params = new URLSearchParams();

  params.set('view', view.view_id);

  if (view.span) {
    params.set('span', view.span);
  }

  if (view.sort) {
    params.set('sort', view.sort);
  }

  return `/search?${params.toString()}`;
};
