// eslint-disable-next-line import/no-cycle
import { hdelete, hput, joinAllUri } from 'api';

export type PermissionData = { privilege: string; user_id: string[] };

type ParentUri = (id: string) => string;

export const createPermissionApi = <T>(parentUri: ParentUri) => {
  const uri = (id: string) => {
    return joinAllUri(parentUri(id), 'permission');
  };

  return {
    put: (id: string, data: PermissionData): Promise<T> => {
      return hput<T>(uri(id), data);
    },

    delete: (id: string, data: PermissionData): Promise<T> => {
      return hdelete<T>(uri(id), data);
    }
  };
};
