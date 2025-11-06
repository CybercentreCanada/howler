import type { IndicatorEmail } from './IndicatorEmail';
import type { IndicatorFile } from './IndicatorFile';

/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface ThreatIndicator {
  confidence?: string;
  description?: string;
  email?: IndicatorEmail;
  file?: IndicatorFile;
  first_seen?: string;
  ip?: string;
  last_seen?: string;
  port?: number;
  provider?: string;
  reference?: string;
  scanner_stats?: number;
  sightings?: number;
  type?: string;
}
