import type { AutonomousSystems } from './AutonomousSystems';
import type { DestinationOriginal } from './DestinationOriginal';
import type { Geo } from './Geo';
import type { Nat } from './Nat';
import type { User } from './User';

/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface ObservableDestination {
  address?: string;
  autonomous_systems?: AutonomousSystems;
  bytes?: number;
  domain?: string;
  geo?: Geo;
  ip?: string;
  mac?: string;
  nat?: Nat;
  original?: DestinationOriginal;
  packets?: number;
  port?: number;
  user?: User;
}
