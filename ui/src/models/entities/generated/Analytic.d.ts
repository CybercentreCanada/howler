import type { Comment } from './Comment';
import type { Notebook } from './Notebook';
import type { TriageSettings } from './TriageSettings';

/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface Analytic {
  analytic_id?: string;
  comment?: Comment[];
  contributors?: string[];
  description?: string;
  detections?: string[];
  name?: string;
  notebooks?: Notebook[];
  owner?: string;
  rule?: string;
  rule_crontab?: string;
  rule_type?: string;
  triage_settings?: TriageSettings;
}
