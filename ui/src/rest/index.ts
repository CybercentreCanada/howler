import type { HowlerResponse } from 'api';

export type RestResponse<R> = [HowlerResponse<R>, number, { [index: string]: any }];

export default interface RestClient {
  fetch<R>(
    url: string,
    method: 'get' | 'post' | 'put' | 'delete' | 'patch',
    body?: any,
    params?: URLSearchParams,
    headers?: HeadersInit,
    signal?: AbortSignal
  ): Promise<RestResponse<R> | undefined>;
  // eslint-disable-next-line semi
}
