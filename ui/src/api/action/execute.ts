import { hpost, joinAllUri, joinUri } from 'api';
import { uri as parentUri } from 'api/action';
import type { ActionReport, ActionRequest } from 'models/ActionTypes';

export const uri = (id?: string) => {
  return id ? joinAllUri(parentUri(), id, 'execute') : joinUri(parentUri(), 'execute');
};

export const post = (data: ActionRequest) => {
  if (data.action_id) {
    return hpost<ActionReport>(uri(data.action_id), { request_id: data.request_id, query: data.query });
  } else {
    return hpost<ActionReport>(uri(), {
      request_id: data.request_id,
      query: data.query,
      operations: data.operations
    });
  }
};
