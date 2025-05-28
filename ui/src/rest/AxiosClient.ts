import type { HowlerResponse } from 'api';
import type { AxiosInstance, AxiosRequestConfig, AxiosRequestHeaders } from 'axios';
import axios, { AxiosError } from 'axios';
import axiosRetry, { exponentialDelay, isNetworkError } from 'axios-retry';
import type RestClient from 'rest';
import { getAxiosCache, setAxiosCache } from 'utils/sessionStorage';

class AxiosCache {
  constructor(_axios: AxiosInstance) {
    _axios.interceptors.response.use(async res => {
      const cache = getAxiosCache();

      if (res.status >= 200 && res.status < 300 && res.headers.etag) {
        setAxiosCache(res.headers.etag, res.data);
      }

      if (res.status === 304) {
        const etag = res.config.headers['If-Match'] as string;
        if (etag) {
          res.data = cache[etag];
        }
      }

      return res;
    });
  }
}

export default class AxiosClient implements RestClient {
  private cache: AxiosCache;

  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      validateStatus: status => (status >= 200 && status < 300) || status === 304
    });

    this.cache = new AxiosCache(this.client);

    axiosRetry(this.client, {
      retries: 3,
      retryCondition: err => {
        return (
          // Don't retry 502s, as we assume the server handles retries in those cases
          isNetworkError(err) || (err?.response?.status >= 500 && err?.response?.status !== 502)
        );
      },
      retryDelay: exponentialDelay
    });
  }

  public async fetch<R>(
    url: string,
    method: 'get' | 'post' | 'put' | 'delete' | 'patch' = 'get',
    body?: any,
    params?: URLSearchParams,
    headers?: HeadersInit
  ): Promise<[HowlerResponse<R>, number, { [index: string]: any }]> {
    const config: AxiosRequestConfig = {
      url,
      params,
      method,
      withCredentials: true,
      data: JSON.stringify(body),
      headers: headers as AxiosRequestHeaders
    };

    try {
      const response = await this.client(config);
      return [response.data, response.status, response.headers];
    } catch (e) {
      if (e instanceof AxiosError && e.response?.data) {
        return [e.response.data, e.response.status, e.response.headers];
      }

      throw e;
    }
  }
}
