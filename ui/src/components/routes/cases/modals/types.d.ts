import type { Event } from 'models/entities/generated/Event';
import type { Hit } from 'models/entities/generated/Hit';

export interface FolderOption {
  id: string;
  label: string;
}

export interface RecordEntry {
  record: Hit | Event;
  parent: string | null;
  name: string;
}
