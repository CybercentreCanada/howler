import { hdelete, hget, hpost, joinAllUri, joinUri, uri as parentUri } from 'api';
import * as assign from 'api/hit/assign';
import * as comments from 'api/hit/comments';
import * as labels from 'api/hit/labels';
import * as overwrite from 'api/hit/overwrite';
import * as transition from 'api/hit/transition';
import type { Hit } from 'models/entities/generated/Hit';

export type HitActionBody = {
  value: string;
};

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

export const get = (id: string): Promise<Hit> => {
  return hget(uri(id));
};

interface PostResponse {
  valid: Hit[];
  invalid: {
    input: Hit;
    error: string;
  }[];
}

export const post = (hits: Hit[]): Promise<PostResponse> => {
  return hpost(uri(), hits);
};

export const del = (ids: string[]): Promise<{ success: boolean }> => {
  return hdelete(uri(), ids);
};

export { assign, comments, labels, overwrite, transition };
