import type { HowlerResponse } from 'api';

export type RestResponse<R> = [HowlerResponse<R>, number, { [index: string]: any }];

export default interface RestClient {
  fetch<R>(
    url: string,
    method: 'get' | 'post' | 'put' | 'delete',
    body?: any,
    params?: URLSearchParams,
    headers?: HeadersInit
  ): Promise<RestResponse<R> | null>;
  // eslint-disable-next-line semi
}
