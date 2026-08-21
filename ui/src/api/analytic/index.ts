import { hdelete, hget, hput, joinAllUri, joinUri, uri as parentUri, type HowlerRefreshParam } from 'api';
import * as comments from 'api/analytic/comments';
import * as favourite from 'api/analytic/favourite';
import * as notebooks from 'api/analytic/notebooks';
import * as owner from 'api/analytic/owner';
import type { Analytic } from 'models/entities/generated/Analytic';

export type EditOptions = Pick<Analytic, 'description' | 'triage_settings'>;

export const uri = (id?: string) => {
  return id ? joinAllUri(parentUri(), 'analytic', id) : joinUri(parentUri(), 'analytic');
};

export const get = ((id?: string) => {
  return id ? hget<Analytic>(uri(id)) : hget<Analytic[]>(uri());
}) as {
  (id: string): ReturnType<typeof hget<Analytic>>;
  (id?: undefined): ReturnType<typeof hget<Analytic[]>>;
};

export const put = (id: string, editData: EditOptions, refresh?: HowlerRefreshParam) => {
  return hput<Analytic>(uri(id), editData, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export const del = (id: string, refresh?: HowlerRefreshParam) => {
  return hdelete(uri(id), undefined, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export { comments, favourite, notebooks, owner };
