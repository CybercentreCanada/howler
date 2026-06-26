import type { Event } from 'models/entities/generated/Event';
import type { Hit } from 'models/entities/generated/Hit';

export const getUserList = (record: Hit | Event): Set<string> => {
  const ids = new Set<string>();
  if (record) {
    record.howler?.log?.forEach(l => ids.add(l.user));
    record.howler?.comment?.forEach(c => ids.add(c.user), ids);
  }
  return ids;
};
