import * as action from 'api/action';
import * as analytic from 'api/analytic';
import * as auth from 'api/auth';
import * as configs from 'api/configs';
import * as dossier from 'api/dossier';
import * as help from 'api/help';
import * as hit from 'api/hit';
import * as notebook from 'api/notebook';
import * as overview from 'api/overview';
import * as search from 'api/search';
import * as socket from 'api/socket';
import * as template from 'api/template';
import * as user from 'api/user';
import * as v2 from 'api/v2';
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
  socket,
  template,
  user,
  view,
  notebook,
  v2
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

export type HowlerRefreshParam = 'true' | 'false' | 'wait_for';

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
  // skip validation if we're hitting the socket endpoints
  if (_uri.startsWith('/socket')) {
    return _uri;
  }

  return _uri.startsWith('/api') ? _uri : `${uri()}/${_uri.replace(/\/$/, '')}`;
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
 * Build the XSRF and authorization headers shared by Howler API requests.
 */
const getAuthHeaders = (): Record<string, string> => {
  const authToken = getLocalStored<string>(StorageKey.APP_TOKEN);
  const xsrfToken = getXSRFCookie();

  return {
    ...(xsrfToken ? { 'X-XSRF-TOKEN': xsrfToken } : {}),
    ...(authToken ? { Authorization: `Bearer ${authToken}` } : {})
  };
};

/**
 * Handle a 401 response by refreshing the access token and retrying the request, or by sending the user to the
 * login page when the token cannot be refreshed.
 *
 * @param _uri - the uri that was rejected.
 * @param retry - re-executes the rejected request once the token is refreshed.
 * @returns the result of the retried request, or `undefined` when redirecting to the login page.
 */
const handleUnauthorized = async <T>(_uri: string, retry: () => Promise<T>): Promise<T | undefined> => {
  if (!getLocalStored(StorageKey.NEXT_LOCATION)) {
    setLocalStored(StorageKey.NEXT_LOCATION, window.location.pathname);
    setLocalStored(StorageKey.NEXT_SEARCH, window.location.search);
  }

  const refreshToken = getLocalStored<string>(StorageKey.REFRESH_TOKEN);
  const provider = getLocalStored<string>(StorageKey.PROVIDER);
  if (!_uri.includes('/auth/login') && refreshToken && provider) {
    //Refresh access token if possible
    //And re-execute the previous api call (seamless)
    const refreshResponse = await api.auth.login.post({ refresh_token: refreshToken, provider: provider });

    if (refreshResponse) {
      saveLoginCredential(refreshResponse);
      const result = await retry();

      removeLocalStored(StorageKey.NEXT_LOCATION);
      removeLocalStored(StorageKey.NEXT_SEARCH);

      return result;
    }
  }

  saveLoginCredential({});

  if (window.location.pathname !== '/login') {
    window.location.pathname = '/login';
  }
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
  body?: unknown,
  searchParams?: URLSearchParams,
  requestHeaders?: HeadersInit,
  signal?: AbortSignal
): Promise<R | undefined> => {
  const etags = getSessionStored<Record<string, string>>(StorageKey.ETAG) || {};
  const currentObject = etags[getEtagUrl(_uri)] || null;

  requestHeaders = {
    ...requestHeaders,
    ...(currentObject && setHeaders(currentObject)),
    'Content-Type': 'application/json',
    ...getAuthHeaders()
  };

  // Wait for it ....
  const [json, statusCode, responseHeader] = await client.fetch<R>(
    format(_uri),
    method,
    body,
    searchParams,
    requestHeaders,
    signal
  );

  if (responseHeader.etag) {
    setSessionStored(StorageKey.ETAG, { ...etags, [getEtagUrl(_uri)]: responseHeader.etag });
  }

  if (!json) {
    return;
  }

  // Did it work?
  if (statusCode < 300 || statusCode === 304) {
    return json.api_response;
  }

  if (statusCode === 401) {
    return handleUnauthorized(_uri, () => hfetch<R>(_uri, method, body, searchParams, undefined, signal));
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
 * A single server-sent event received from a Howler streaming endpoint.
 */
export type HowlerStreamEvent = {
  event: string;
  data: unknown;
};

const parseStreamEvent = (frame: string): HowlerStreamEvent | null => {
  let event = 'message';
  const data: string[] = [];

  for (const line of frame.split(/\r?\n/)) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim();
    } else if (line.startsWith('data:')) {
      data.push(line.slice(5).trimStart());
    }
  }

  return data.length ? { event, data: JSON.parse(data.join('\n')) } : null;
};

/**
 * POST to a Howler endpoint that responds with server-sent events, invoking `onEvent` for each event received.
 *
 * Errors thrown by `onEvent` cancel the stream and are rethrown. Expired access tokens are refreshed and the
 * request retried, as with {@link hfetch}.
 *
 * @param _uri - the uri to post to.
 * @param body - the JSON body of the request.
 * @param onEvent - handler called for each parsed event.
 * @param signal - optional signal used to abort the request.
 */
export const hstream = async (
  _uri: string,
  body: unknown,
  onEvent: (event: HowlerStreamEvent) => void,
  signal?: AbortSignal
): Promise<void> => {
  const response = await fetch(format(_uri), {
    method: 'POST',
    credentials: 'same-origin',
    headers: { ...getAuthHeaders(), 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(body),
    signal
  });

  if (response.status === 401) {
    await handleUnauthorized(_uri, () => hstream(_uri, body, onEvent, signal));
    return;
  }

  if (!response.ok || !response.body) {
    const json = (await response.json().catch(() => null)) as HowlerResponse<unknown> | null;
    throw new Error(json?.api_error_message || `Error while streaming ${_uri} - ${response.status}`, { cause: json });
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    for (;;) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });

      const frames = buffer.split(/\r?\n\r?\n/);
      buffer = done ? '' : (frames.pop() ?? '');

      for (const frame of frames) {
        const parsed = parseStreamEvent(frame);
        if (parsed) {
          onEvent(parsed);
        }
      }

      if (done) {
        break;
      }
    }
  } catch (error) {
    await reader.cancel().catch(() => undefined);
    throw error;
  }
};

/**
 * Perform an HTTP GET for the specified uri.
 *
 * This method eventually delegates to {@link hfetch}
 *
 * @param _uri - the uri to fetch.
 * @returns the `api_response` object of the returned {@link HowlerResponse}.
 */
export const hget = <R = any>(
  _uri: string,
  searchParams?: URLSearchParams,
  headers: HeadersInit = {},
  signal?: AbortSignal
) => {
  return hfetch<R>(_uri, 'get', null, searchParams, headers, signal);
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
export const hpost = <R = any>(
  _uri: string,
  body: unknown,
  headers: HeadersInit = {},
  searchParams?: URLSearchParams,
  signal?: AbortSignal
) => {
  return hfetch<R>(_uri, 'post', body, searchParams, headers, signal);
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
export const hput = <R = any>(
  _uri: string,
  body: unknown,
  headers: HeadersInit = {},
  searchParams?: URLSearchParams
) => {
  return hfetch<R>(_uri, 'put', body, searchParams, headers);
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
export const hpatch = <R = any>(
  _uri: string,
  body: unknown,
  headers: HeadersInit = {},
  searchParams?: URLSearchParams
) => {
  return hfetch<R>(_uri, 'patch', body, searchParams, headers);
};

/**
 * Performa an HTTP DELETE for the specified uri.
 *
 * This method eventually delegates to {@link hfetch}
 *
 * @param _uri - the uri to fetch.
 * @returns the `api_response` object of the returned {@link HowlerResponse}.
 */
export const hdelete = async <T = void>(
  _uri: string,
  body: unknown = null,
  headers: HeadersInit = {},
  searchParams?: URLSearchParams
): Promise<T | undefined> => {
  return hfetch<T>(_uri, 'delete', body, searchParams, headers);
};

/**
 * Default export exposing the howler rest api
 */
export default api;
