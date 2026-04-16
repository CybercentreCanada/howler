import type { HowlerResponse } from 'api';
import AxiosClient from 'rest/AxiosClient';
import urlJoin from 'url-join';
import { StorageKey } from 'utils/constants';
import { getStored as getLocalStored } from 'utils/localStorage';

const client = new AxiosClient();
const BASE_URI = '/socket/v1/viewers';

export const get = async (entityId: string): Promise<string[]> => {
  const authToken = getLocalStored(StorageKey.APP_TOKEN);
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`;
  }

  const [json, statusCode] = await client.fetch<string[]>(
    urlJoin(BASE_URI, entityId),
    'get',
    undefined,
    undefined,
    headers
  );
  if (statusCode < 300) {
    return (json as HowlerResponse<string[]>).api_response;
  }

  return [];
};
