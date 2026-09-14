import { pick } from 'lodash-es';
import type { MemberItem, Ownership } from './types';

export const getAllMembers = (item?: Ownership): MemberItem[] =>
  item
    ? Object.entries(pick(item, ['owner', 'admins', 'members'])).flatMap(([privilege, members]) =>
        Array.isArray(members)
          ? members.map(member => [member, privilege] as MemberItem)
          : [[members, privilege] as MemberItem]
      )
    : [];
