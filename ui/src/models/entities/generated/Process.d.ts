import type { CodeSignature } from './CodeSignature';
import type { EntryMeta } from './EntryMeta';
import type { Pe } from './Pe';
import type { ProcessHash } from './ProcessHash';
import type { ProcessParent } from './ProcessParent';
import type { ProcessUser } from './ProcessUser';

/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface Process {
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
  hash?: ProcessHash;
  interactive?: boolean;
  name?: string;
  parent?: ProcessParent;
  pe?: Pe;
  pid?: number;
  same_as_process?: boolean;
  start?: string;
  title?: string;
  uptime?: number;
  user?: ProcessUser;
  working_directory?: string;
}
