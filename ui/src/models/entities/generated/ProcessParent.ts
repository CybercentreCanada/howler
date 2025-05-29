import type { CodeSignature } from './CodeSignature';
import type { EntryMeta } from './EntryMeta';
import type { ParentHash } from './ParentHash';
import type { ParentParent } from './ParentParent';
import type { ParentUser } from './ParentUser';
import type { Pe } from './Pe';

/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface ProcessParent {
  args?: string[];
  args_count?: number;
  code_signature?: CodeSignature;
  command_line?: string;
  end?: string;
  entity_id?: string;
  entry_meta?: EntryMeta;
  env_vars?: { [index: string]: string };
  executable?: string;
  exit_code?: number;
  hash?: ParentHash;
  interactive?: boolean;
  name?: string;
  parent?: ParentParent;
  pe?: Pe;
  pid?: number;
  same_as_process?: boolean;
  start?: string;
  title?: string;
  uptime?: number;
  user?: ParentUser;
  working_directory?: string;
}
