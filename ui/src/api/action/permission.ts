import { hdelete, hput, joinAllUri } from 'api';
import { uri as parentUri } from 'api/action';

type PermissionData = { privilege: string; user_id: string };

export const uri = (id: string) => {
  return joinAllUri(parentUri(id), 'permission');
};

export const put = (id: string, data: PermissionData) => {
  return hput(uri(id), data);
};

const del = (id: string, data: PermissionData) => {
  return hdelete(uri(id), data);
};

export { del as delete };
