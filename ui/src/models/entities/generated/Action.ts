import type { Operation } from './Operation';

/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface Action {
  action_id?: string;
  name?: string;
  operations?: Operation[];
  owner_id?: string;
  query?: string;
  triggers?: string[];
}
