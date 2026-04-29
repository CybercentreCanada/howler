import type { Enrichments } from './Enrichments';
import type { Item } from './Item';
import type { Rule } from './Rule';
import type { Task } from './Task';

/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface Case {
  case_id?: string;
  created?: string;
  end?: string;
  enrichments?: Enrichments;
  escalation?: string;
  indicators?: string[];
  items?: Item[];
  overview?: string;
  participants?: string[];
  rules?: Rule[];
  status?: string;
  start?: string;
  summary?: string;
  targets?: string[];
  tasks?: Task[];
  threats?: string[];
  title?: string;
  updated?: string;
}
