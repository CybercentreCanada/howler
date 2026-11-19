import type { HowlerUser } from 'models/entities/HowlerUser';

type UserIdentity = Pick<HowlerUser, 'username'> & { email?: string | null };

const normalize = (value: string) => value.trim().toLowerCase();

export const groupUserIdentities = <T extends UserIdentity>(users: readonly T[]) => {
  const parents = users.map((_, index) => index);
  const usernames = new Map<string, number>();
  const emails = new Map<string, number>();

  const find = (index: number) => {
    while (parents[index] !== index) {
      parents[index] = parents[parents[index]];
      index = parents[index];
    }

    return index;
  };

  const link = (indices: Map<string, number>, key: string, index: number) => {
    const previous = indices.get(key);
    if (previous === undefined) {
      indices.set(key, index);
      return;
    }

    // Keep the smallest original username as the root of each connected component.
    const currentRoot = find(index);
    const previousRoot = find(previous);
    if (users[currentRoot].username < users[previousRoot].username) {
      parents[previousRoot] = currentRoot;
    } else {
      parents[currentRoot] = previousRoot;
    }
  };

  users.forEach((user, index) => {
    link(usernames, normalize(user.username), index);

    const email = normalize(user.email ?? '');
    if (email) {
      link(emails, email, index);
    }
  });

  const canonicalByUsername = new Map(Array.from(usernames, ([username, index]) => [username, users[find(index)]]));

  return {
    canonicalUsers: Array.from(new Set(canonicalByUsername.values())),
    getCanonicalUser: (username: string) => canonicalByUsername.get(normalize(username))
  };
};
