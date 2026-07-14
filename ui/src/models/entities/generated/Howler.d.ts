import type { HowlerComment } from './HowlerComment';
import type { HowlerDossier } from './HowlerDossier';
import type { Incident } from './Incident';
import type { Labels } from './Labels';
import type { Link } from './Link';
import type { Log } from './Log';
import type { Outline } from './Outline';
import type { Votes } from './Votes';

/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface Howler {
  analytic: string;
  assessment?: string;
  assignment: string;
  bundle_size?: number;
  bundles?: string[];
  comment?: HowlerComment[];
  confidence?: number;
  data?: string[];
  detection?: string;
  dossier?: HowlerDossier[];
  escalation?: string;
  expiry?: string;
  hash: string;
  hits?: string[];
  id: string;
  incidents?: Incident[];
  is_bundle?: boolean;
  labels?: Labels;
  links?: Link[];
  log?: Log[];
  mitigated?: string;
  monitored?: string;
  outline?: Outline;
  rationale?: string;
  related?: string[];
  reliability?: number;
  reported?: string;
  score?: number;
  scrutiny?: string;
  severity?: number;
  status?: string;
  viewers?: string[];
  volume?: number;
  votes?: Votes;
}
