import type { HowlerResponse } from 'api';
import type RestClient from 'rest';

export default class FetchClient implements RestClient {
  public async fetch<R>(
    url: string,
    method: 'get' | 'post' | 'put' | 'delete' = 'get',
    body?: any,
    params?: URLSearchParams,
    headers?: HeadersInit
  ): Promise<[HowlerResponse<R>, number, { [index: string]: any }] | null> {
    const _url = `${url}${params ? `?${params.toString()}` : ''}`;
    const request: RequestInit = {
      method,
      credentials: 'same-origin',
      headers: headers
    };

    if (method !== 'get' && body) {
      request.body = JSON.stringify(body);
    }

    const response = await fetch(_url, request);

    if (response.status === 204) {
      return null;
    }

    const json = (await response.json()) as HowlerResponse<R>;
    return [json, response.status, response.headers];
  }
}
