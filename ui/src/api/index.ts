import * as action from 'api/action';
import * as analytic from 'api/analytic';
import * as auth from 'api/auth';
import * as configs from 'api/configs';
import * as dossier from 'api/dossier';
import * as help from 'api/help';
import * as hit from 'api/hit';
import * as overview from 'api/overview';
import * as search from 'api/search';
import * as template from 'api/template';
import * as user from 'api/user';
import * as view from 'api/view';
import AxiosClient from 'rest/AxiosClient';
import urlJoin from 'url-join';
import { StorageKey } from 'utils/constants';
import {
  getStored as getLocalStored,
  removeStored as removeLocalStored,
  saveLoginCredential,
  setStored as setLocalStored
} from 'utils/localStorage';
import { getStored as getSessionStored, setStored as setSessionStored } from 'utils/sessionStorage';
import getXSRFCookie from 'utils/xsrf';

/**
 * Concrete Rest HTTP client implementation.
 */
const client = new AxiosClient();

/**
 * Defining the default export exposing all children routes of '/api/v1/'.
 */
// prettier-ignore
const api = {
  action,
  analytic,
  auth,
  configs,
  dossier,
  help,
  hit,
  overview,
  search,
  template,
  user,
  view,
};

/**
 * The specification interface of an Howler HTTP response.
 */
export type HowlerResponse<R> = {
  api_response: R;
  api_error_message: string;
  api_server_version: string;
  api_status_code: number;
};

/**
 * The base section of the Howler API uri.
 *
 * `/api/v1/`
 */
export const uri = () => {
  return '/api/v1';
};

/**
 * Format/Adapt the specified URI to an Howler API uri.
 *
 * Ensure it starts with '/api/v1' and doesn't end with a '/'.
 *
 * @param _uri - the uri to format.
 * @returns `string` - properly formatted howler uri.
 */
const format = (_uri: string): string => {
  return _uri.startsWith(uri()) ? _uri : `${uri()}/${_uri.replace(/\/$/, '')}`;
};

/**
 * Append series of search parameters to the specified uri.
 *
 * @param _uri - the base uri.
 * @param searchParams  -  a list of search parameters to join with the uri.
 * @returns a uri with the search parameters.
 */
export const joinParams = (_uri: string, searchParams?: URLSearchParams): string => {
  return `${_uri}${searchParams ? `${_uri.indexOf('?') > 0 ? '&' : '?'}${searchParams.toString()}` : ''}`;
};

/**
 * Join two uri and then join them with the specified search parameters.
 *
 * This function will format the resulting uri section using {@link format}.
 *
 * This function will join the specified parameters using {@link joinParams}
 *
 * @param uri1 the first section of the uri.
 * @param uri2 the second section of the uri.
 * @param searchParams the search parameters to append to the uri.
 * @returns a uri that joins `uri1` and `uri2` with the specified `_search` parameters.
 */
export const joinUri = (uri1: string, uri2: string, searchParams?: URLSearchParams): string => {
  const _uri = format(urlJoin(uri1, uri2));
  return searchParams ? joinParams(_uri, searchParams) : _uri;
};

/**
 * joinUrl all params together
 *
 * @returns a uri generated from all params
 */
export const joinAllUri = (...urlParts: string[]): string => {
  return urlJoin(...urlParts);
};

/**
 * Create the required headers object for attaching to the request
 *
 * @param ifMatch a value for the If-Match header
 */
export const setHeaders = (ifMatch?: string): HeadersInit => {
  const headers: HeadersInit = {};
  if (ifMatch) {
    headers['If-Match'] = ifMatch;
  }
  return headers;
};

const getEtagUrl = (_uri: string): string => {
  if (_uri.startsWith('/api/v1/hit')) {
    return _uri.replace(/.+hit\/(.+?)$/g, '$1').split('/')[0];
  }

  return _uri;
};

/**
 * Generic FETCH implementation for HOWLER API.
 *
 * This function will format the specified `url` with {@link format} before issuing the fetch.
 *
 * @param _uri - the uri to fetch.
 * @param method - the http method to use.
 * @param body - the body of the request.
 * @returns the `api_response` object of the returned {@link HowlerResponse}.
 */
export const hfetch = async <R>(
  _uri: string,
  method: 'get' | 'post' | 'put' | 'delete' | 'patch' = 'get',
  body?: any,
  searchParams?: URLSearchParams,
  requestHeaders?: HeadersInit
): Promise<R> => {
  const authToken = getLocalStored(StorageKey.APP_TOKEN);
  const etags = getSessionStored(StorageKey.ETAG) || {};
  const currentObject = etags[getEtagUrl(_uri)] || null;

  requestHeaders = {
    ...requestHeaders,
    ...(currentObject && setHeaders(currentObject)),
    'Content-Type': 'application/json',
    'X-XSRF-TOKEN': getXSRFCookie()
  };

  if (authToken) {
    requestHeaders = { ...requestHeaders, Authorization: `Bearer ${authToken}` };
  }

  // Wait for it ....
  const [json, statusCode, responseHeader] = await client.fetch<R>(
    format(_uri),
    method,
    body,
    searchParams,
    requestHeaders
  );

  if (responseHeader.etag) {
    setSessionStored(StorageKey.ETAG, { ...etags, [getEtagUrl(_uri)]: responseHeader.etag });
  }

  if (!json) {
    return null;
  }

  // Did it work?
  if (statusCode < 300 || statusCode === 304) {
    return json.api_response;
  }

  if (statusCode === 401) {
    if (!getLocalStored(StorageKey.NEXT_LOCATION)) {
      setLocalStored(StorageKey.NEXT_LOCATION, window.location.pathname);
      setLocalStored(StorageKey.NEXT_SEARCH, window.location.search);
    }

    if (!_uri.includes('/auth/login') && getLocalStored(StorageKey.REFRESH_TOKEN)) {
      //Refresh access token if possible
      //And re-execute the previous api call (seamless)
      const refreshToken: string = getLocalStored(StorageKey.REFRESH_TOKEN);
      const provider: string = getLocalStored(StorageKey.PROVIDER);
      const refreshResponse = await api.auth.login.post({ refresh_token: refreshToken, provider: provider });

      if (refreshResponse) {
        saveLoginCredential(refreshResponse);
        const result = await hfetch<R>(_uri, method, body, searchParams);

        removeLocalStored(StorageKey.NEXT_LOCATION);
        removeLocalStored(StorageKey.NEXT_SEARCH);

        return result;
      }
    }

    saveLoginCredential({});

    if (window.location.pathname !== '/login') {
      window.location.pathname = '/login';
    }
    return;
  }

  // Throw it back.
  throw new Error(
    json.api_error_message || (json as unknown as string) || `Error while fetching ${_uri} - ${method.toUpperCase()}`,
    {
      cause: json
    }
  );
};

/**
 * Perform an HTTP GET for the specified uri.
 *
 * This method eventually delegates to {@link hfetch}
 *
 * @param _uri - the uri to fetch.
 * @returns the `api_response` object of the returned {@link HowlerResponse}.
 */
export const hget = <R = any>(_uri: string, searchParams?: URLSearchParams, headers: HeadersInit = {}): Promise<R> => {
  return hfetch(_uri, 'get', null, searchParams, headers);
};

/**
 * Perform an HTTP POST for the specified uri and body data.
 *
 * This method eventually delegates to {@link hfetch}
 *
 * @param _uri - the uri to fetch.
 * @param body - the body of the request.
 * @returns the `api_response` object of the returned {@link HowlerResponse}.
 */
export const hpost = <R = any>(_uri: string, body: any, headers: HeadersInit = {}): Promise<R> => {
  return hfetch(_uri, 'post', body, undefined, headers);
};

/**
 * Peform an HTTP PUT for the specified uri and body data.
 *
 * This method eventually delegates to {@link hfetch}
 *
 * @param _uri - the uri to fetch.
 * @param body - the body of the request.
 * @returns the `api_response` object of the returned {@link HowlerResponse}.
 */
export const hput = <R = any>(_uri: string, body: any, headers: HeadersInit = {}): Promise<R> => {
  return hfetch(_uri, 'put', body, undefined, headers);
};

/**
 * Peform an HTTP PATCH for the specified uri and body data.
 *
 * This method eventually delegates to {@link hfetch}
 *
 * @param _uri - the uri to fetch.
 * @param body - the body of the request.
 * @returns the `api_response` object of the returned {@link HowlerResponse}.
 */
export const hpatch = <R = any>(_uri: string, body: any, headers: HeadersInit = {}): Promise<R> => {
  return hfetch(_uri, 'patch', body, undefined, headers);
};

/**
 * Performa an HTTP DELETE for the specified uri.
 *
 * This method eventually delegates to {@link hfetch}
 *
 * @param _uri - the uri to fetch.
 * @returns the `api_response` object of the returned {@link HowlerResponse}.
 */
export const hdelete = <R = any>(_uri: string, body = null, headers: HeadersInit = {}): Promise<R> => {
  return hfetch(_uri, 'delete', body, undefined, headers);
};

/**
 * Default export exposing the howler rest api
 */
export default api;
