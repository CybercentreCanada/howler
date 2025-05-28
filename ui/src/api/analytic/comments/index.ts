import { hdelete, hget, hpost, hput, joinAllUri, joinUri } from 'api';
import { uri as parentUri } from 'api/analytic';
import type { Analytic } from 'models/entities/generated/Analytic';
import type { Comment } from 'models/entities/generated/Comment';
import * as react from './react';

export const uri = (analytic: string, comment?: string) => {
  return comment ? joinAllUri(parentUri(analytic), 'comments', comment) : joinUri(parentUri(analytic), 'comments');
};

export const get = (analytic: string, comment: string): Promise<Comment> => {
  return hget(uri(analytic, comment));
};

export const put = (analytic: string, comment: string, value: string): Promise<{ success: boolean }> => {
  return hput(uri(analytic, comment), { value });
};

export const post = (analytic: string, value: string, detection?: string): Promise<Analytic> => {
  return hpost(uri(analytic), { value, detection });
};

export const del = (analytic: string, comments: string[]): Promise<{ success: boolean }> => {
  return hdelete(uri(analytic), comments);
};

export { react };
