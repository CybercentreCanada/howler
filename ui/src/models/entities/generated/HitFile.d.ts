import type { CodeSignature } from './CodeSignature';
import type { Elf } from './Elf';
import type { FileHash } from './FileHash';
import type { Pe } from './Pe';

/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface HitFile {
  accessed?: string;
  attributes?: string[];
  code_signature?: CodeSignature;
  created?: string;
  ctime?: string;
  device?: string;
  directory?: string;
  drive_letter?: string;
  elf?: Elf;
  extension?: string;
  fork_name?: string;
  gid?: string;
  group?: string;
  hash?: FileHash;
  inode?: string;
  mime_type?: string;
  mode?: string;
  mtime?: string;
  name?: string;
  owner?: string;
  path?: string;
  pe?: Pe;
  size?: number;
  target_path?: string;
  type?: string;
  uid?: string;
}
