// eslint-disable-next-line import/no-cycle
import { hdelete, hput, joinAllUri } from 'api';

export type PermissionData = { privilege: string; user_id: string[] };

type ParentUri = (id: string) => string;

const createPermissionsApi = <T>(parentUri: ParentUri) => {
  const uri = (id: string) => joinAllUri(parentUri(id), 'permission');

  return {
    put: (id: string, data: PermissionData) => hput<T>(uri(id), data),
    delete: (id: string, data: PermissionData) => hdelete<T>(uri(id), data)
  };
};

export default createPermissionsApi;
