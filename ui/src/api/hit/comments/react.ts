// eslint-disable-next-line import/no-cycle
import { hdelete, hput, joinUri } from 'api';
import { uri as parentUri } from 'api/hit/comments';

export const uri = (hit: string, comment: string) => {
  return joinUri(parentUri(hit, comment), 'react');
};

export const put = (hit: string, comment: string, type: string): Promise<boolean> => {
  return hput(uri(hit, comment), { type });
};

export const del = (hit: string, comment: string): Promise<boolean> => {
  return hdelete(uri(hit, comment));
};
