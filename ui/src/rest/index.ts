import type { HowlerResponse } from 'api';

export default interface RestClient {
  fetch<R>(
    url: string,
    method: 'get' | 'post' | 'put' | 'delete',
    body?: any,
    params?: URLSearchParams,
    headers?: HeadersInit
  ): Promise<[HowlerResponse<R>, number, { [index: string]: any }]>;
  // eslint-disable-next-line semi
}
