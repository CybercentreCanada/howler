import type { Event } from 'models/entities/generated/Event';
import type { Hit } from 'models/entities/generated/Hit';

export interface RecordEntry {
  record: Hit | Event;
  path: string;
  title: string;
}
