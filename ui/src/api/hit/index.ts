import { hdelete, hget, hpost, joinAllUri, joinUri, uri as parentUri, type HowlerRefreshParam } from 'api';
import * as assign from 'api/hit/assign';
import * as comments from 'api/hit/comments';
import * as labels from 'api/hit/labels';
import * as overwrite from 'api/hit/overwrite';
import * as transition from 'api/hit/transition';
import type { Hit } from 'models/entities/generated/Hit';

export type LabelActionBody = {
  value: string[];
};

export type HitTransitionBody = {
  transition: string;
  data: { [key: string]: any };
};

export type HitActionResponse = {
  success: boolean;
};

export const uri = (id?: string): string => {
  return id ? joinAllUri(parentUri(), 'hit', id) : joinUri(parentUri(), 'hit');
};

export const get = <T extends Hit>(id: string, metadata?: string[]) => {
  const params = new URLSearchParams();

  if (metadata) {
    params.append('metadata', metadata.join(','));
  }

  return hget<T>(uri(id), params);
};

interface PostResponse {
  valid: Hit[];
  invalid: {
    input: Hit;
    error: string;
  }[];
}

export const post = (hits: Hit[], refresh?: HowlerRefreshParam) => {
  return hpost<PostResponse>(uri(), hits, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export const del = (ids: string[], refresh?: HowlerRefreshParam) => {
  return hdelete(uri(), ids, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export { assign, comments, labels, overwrite, transition };
