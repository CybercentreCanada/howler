import { hget, hpost, joinUri } from 'api';
import { uri as parentUri } from 'api/auth';
import { MY_LOCAL_STORAGE_PREFIX, StorageKey } from 'utils/constants';

export type PostLoginBody = {
  user?: string;
  password?: string;
  refresh_token?: string;
  provider?: string;
};

export type LoginResponse = {
  app_token?: string;
  refresh_token?: string;
  provider?: string;
};

export const uri = (searchParams?: URLSearchParams) => {
  return joinUri(parentUri(), 'login', searchParams);
};

export const post = (body: PostLoginBody): Promise<LoginResponse> => {
  return hpost(uri(), body);
};

export const get = (search: URLSearchParams): Promise<LoginResponse> => {
  const nonce = localStorage.getItem(`${MY_LOCAL_STORAGE_PREFIX}.${StorageKey.LOGIN_NONCE}`);

  if (nonce) {
    console.log('Adding nonce');
    search.set('nonce', JSON.parse(nonce));
    localStorage.removeItem(`${MY_LOCAL_STORAGE_PREFIX}.${StorageKey.LOGIN_NONCE}`);
  }

  return hget(uri(), search);
};
