import type { Egress } from './Egress';
import type { Interface } from './Interface';
import type { ObserverIngress } from './ObserverIngress';

/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface ObservableObserver {
  egress?: Egress;
  hostname?: string;
  ingress?: ObserverIngress;
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
