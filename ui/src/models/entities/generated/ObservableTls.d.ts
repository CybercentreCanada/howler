import type { Client } from './Client';
import type { TlsServer } from './TlsServer';

/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface ObservableTls {
  client?: Client;
  server?: TlsServer;
  version?: string;
  version_protocol?: string;
}
