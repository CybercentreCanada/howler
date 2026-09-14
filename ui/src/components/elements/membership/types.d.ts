export interface Ownership {
  owner?: string;
  admins?: string[];
  members?: string[];
}

export type MemberItem = [string, 'owner' | 'admins' | 'members'];
