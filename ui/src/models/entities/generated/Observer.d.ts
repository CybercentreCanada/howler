import type { Egress } from './Egress';
import type { Ingress } from './Ingress';
import type { Interface } from './Interface';

/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface Observer {
  egress?: Egress;
  hostname?: string;
  ingress?: Ingress;
  interface?: Interface;
  ip?: string[];
  mac?: string[];
  name?: string;
  product?: string;
  serial_number?: string;
  type?: string;
  vendor?: string;
  version?: string;
}
