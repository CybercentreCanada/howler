import type { CloudAccount } from './CloudAccount';
import type { Instance } from './Instance';
import type { Machine } from './Machine';
import type { Project } from './Project';
import type { Service } from './Service';

/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface Cloud {
  account?: CloudAccount;
  availability_zone?: string;
  instance?: Instance;
  machine?: Machine;
  project?: Project;
  provider?: string;
  region?: string;
  service?: Service;
  tenant_id?: string;
}
