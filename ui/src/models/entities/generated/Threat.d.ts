import type { Enrichment } from './Enrichment';
import type { Feed } from './Feed';
import type { Software } from './Software';
import type { ThreatGroup } from './ThreatGroup';
import type { ThreatIndicator } from './ThreatIndicator';
import type { ThreatTactic } from './ThreatTactic';
import type { ThreatTechnique } from './ThreatTechnique';

/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface Threat {
  enrichments?: Enrichment[];
  feed?: Feed;
  framework?: string;
  group?: ThreatGroup;
  indicator?: ThreatIndicator;
  software?: Software;
  tactic?: ThreatTactic;
  technique?: ThreatTechnique;
}
