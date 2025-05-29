import { hdelete, hpost, joinAllUri } from 'api';
import { uri as parentUri } from 'api/analytic';

export const uri = (id: string) => {
  return joinAllUri(parentUri(), id, 'favourite');
};

export const del = (id: string): Promise<{ success: boolean }> => {
  return hdelete(uri(id));
};

export const post = (id: string): Promise<{ success: boolean }> => {
  return hpost(uri(id), {});
};
