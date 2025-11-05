import type { Answer } from './Answer';
import type { Question } from './Question';

/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface Dns {
  answers?: Answer[];
  header_flags?: string[];
  id?: string;
  op_code?: string;
  question?: Question;
  resolved_ip?: string[];
  response_code?: string;
  type?: string;
}
