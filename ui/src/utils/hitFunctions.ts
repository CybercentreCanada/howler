import type { Hit } from 'models/entities/generated/Hit';
import type { Observable } from 'models/entities/generated/Observable';

export const getUserList = (record: Hit | Observable): Set<string> => {
  const ids = new Set<string>();
  if (record) {
    record.howler?.log?.forEach(l => ids.add(l.user));
    record.howler?.comment?.forEach(c => ids.add(c.user), ids);
  }
  return ids;
};
