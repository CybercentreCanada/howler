import type { Header } from './Header';
import type { Section } from './Section';
import type { Segment } from './Segment';

/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface Elf {
  architecture?: string;
  byte_order?: string;
  cpu_type?: string;
  creation_date?: string;
  exports?: string[];
  header?: Header;
  imports?: string[];
  sections?: Section[];
  segments?: Segment[];
  shared_libraries?: string[];
  telfhash?: string;
}
