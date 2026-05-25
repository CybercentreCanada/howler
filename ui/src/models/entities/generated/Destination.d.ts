import type { AutonomousSystems } from './AutonomousSystems';
import type { Geo } from './Geo';
import type { Nat } from './Nat';
import type { Original } from './Original';
import type { User } from './User';

/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface Destination {
  address?: string;
  autonomous_systems?: AutonomousSystems;
  bytes?: number;
  domain?: string;
  geo?: Geo;
  ip?: string;
  mac?: string;
  nat?: Nat;
  original?: Original;
  packets?: number;
  port?: number;
  user?: User;
}
