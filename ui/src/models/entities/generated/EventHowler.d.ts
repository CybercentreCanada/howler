import type { HowlerComment } from './HowlerComment';
import type { Log } from './Log';
import type { Outline } from './Outline';

/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface EventHowler {
  comment?: HowlerComment[];
  data?: string[];
  escalation?: string;
  expiry?: string;
  hash: string;
  id: string;
  log?: Log[];
  outline?: Outline;
  related?: string[];
  score?: number;
}
