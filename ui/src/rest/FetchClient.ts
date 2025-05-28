import type { HowlerResponse } from 'api';
import type RestClient from 'rest';

export default class FetchClient implements RestClient {
  public async fetch<R>(
    url: string,
    method: 'get' | 'post' | 'put' | 'delete' = 'get',
    body?: any,
    params?: URLSearchParams,
    headers?: HeadersInit
  ): Promise<[HowlerResponse<R>, number, { [index: string]: any }]> {
    const _url = `${url}${params ? `?${params.toString()}` : ''}`;
    const response = await fetch(_url, {
      method,
      credentials: 'same-origin',
      headers: headers,
      body: body ? JSON.stringify(body) : null
    });

    if (response.status === 204) {
      return null;
    }

    const json = (await response.json()) as HowlerResponse<R>;
    return [json, response.status, response.headers];
  }
}
