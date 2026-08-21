import { hdelete, hput, joinAllUri, type HowlerRefreshParam } from 'api';
import type { LabelActionBody } from 'api/hit';
import { uri as parentUri } from 'api/hit';
import type { Hit } from 'models/entities/generated/Hit';

export const uri = (id: string, category: string) => {
  return joinAllUri(parentUri(), id, 'labels', category);
};

export const put = (id: string, category: string, body: LabelActionBody, refresh?: HowlerRefreshParam) => {
  return hput<Hit>(uri(id, category), body, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export const del = (id: string, category: string, body: LabelActionBody, refresh?: HowlerRefreshParam) => {
  return hdelete(uri(id, category), body, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};
