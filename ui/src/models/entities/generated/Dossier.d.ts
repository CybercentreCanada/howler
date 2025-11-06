import type { Lead } from './Lead';
import type { Pivot } from './Pivot';

/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface Dossier {
  dossier_id?: string;
  leads?: Lead[];
  owner?: string;
  pivots?: Pivot[];
  query?: string;
  title?: string;
  type?: string;
}
