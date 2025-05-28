import type { Hit } from 'models/entities/generated/Hit';

export const getUserList = (hit: Hit): Set<string> => {
  const ids = new Set<string>();
  if (hit) {
    hit.howler?.log?.forEach(l => ids.add(l.user));
    hit.howler?.comment?.forEach(c => ids.add(c.user), ids);
  }
  return ids;
};
