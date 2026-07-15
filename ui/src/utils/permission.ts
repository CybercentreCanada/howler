export type PermissionData = { privilege: string; user_id: string };

type ParentUri = (id: string) => string;
type JoinAllUri = (...parts: string[]) => string;
type PutRequest = (uri: string, data: PermissionData) => Promise<unknown>;
type DeleteRequest = (uri: string, data: PermissionData) => Promise<unknown>;

export const createPermissionApi = (
  parentUri: ParentUri,
  joinAllUri: JoinAllUri,
  putRequest: PutRequest,
  deleteRequest: DeleteRequest
) => {
  const uri = (id: string) => {
    return joinAllUri(parentUri(id), 'permission');
  };

  return {
    put: (id: string, data: PermissionData) => {
      return putRequest(uri(id), data);
    },
    delete: (id: string, data: PermissionData) => {
      return deleteRequest(uri(id), data);
    }
  };
};
