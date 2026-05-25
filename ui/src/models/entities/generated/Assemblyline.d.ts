import type { Antivirus } from './Antivirus';
import type { Attribution } from './Attribution';
import type { Behaviour } from './Behaviour';
import type { Domain } from './Domain';
import type { Heuristic } from './Heuristic';
import type { Mitre } from './Mitre';
import type { Uri } from './Uri';
import type { Yara } from './Yara';

/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface Assemblyline {
  antivirus?: Antivirus[];
  attribution?: Attribution[];
  behaviour?: Behaviour[];
  domain?: Domain[];
  heuristic?: Heuristic[];
  mitre?: Mitre;
  uri?: Uri[];
  yara?: Yara[];
}
