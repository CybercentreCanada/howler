import { describe, expect, it } from 'vitest';

import { groupUserIdentities } from './userIdentity';

describe('groupUserIdentities', () => {
  it('groups usernames ignoring case and whitespace', () => {
    const users = [
      { username: 'jdoe ', email: 'alias@example.com' },
      { username: 'JDOE', email: 'original@example.com' }
    ];
    const { canonicalUsers, getCanonicalUser } = groupUserIdentities(users);

    expect(canonicalUsers).toEqual([users[1]]);
    expect(getCanonicalUser(' jDoE ')?.username).toBe('JDOE');
  });

  it('groups matching emails ignoring case and whitespace', () => {
    const users = [
      { username: 'jdoe1', email: ' JDOE@EXAMPLE.COM ' },
      { username: 'jdoe', email: 'jdoe@example.com' }
    ];
    const { canonicalUsers, getCanonicalUser } = groupUserIdentities(users);

    expect(canonicalUsers).toEqual([users[1]]);
    expect(getCanonicalUser('jdoe1')?.username).toBe('jdoe');
  });

  it('groups transitively across username and email matches', () => {
    const users = [
      { username: 'chris', email: 'first@example.com' },
      { username: 'amy', email: 'second@example.com' },
      { username: 'Bryan', email: 'first@example.com' },
      { username: 'bryan', email: 'second@example.com' }
    ];

    for (const order of [users, [...users].reverse()]) {
      const { canonicalUsers, getCanonicalUser } = groupUserIdentities(order);

      // Plain string comparison places uppercase B before lowercase a.
      expect(canonicalUsers).toEqual([users[2]]);
      for (const { username } of users) {
        expect(getCanonicalUser(username)?.username).toBe('Bryan');
      }
    }
  });

  it('does not group missing or empty emails unless the usernames match', () => {
    const users = [
      { username: 'amy' },
      { username: 'AMY', email: null },
      { username: 'bryan', email: null },
      { username: 'chris', email: '' },
      { username: 'dan', email: '   ' }
    ];
    const { canonicalUsers, getCanonicalUser } = groupUserIdentities(users);

    expect(canonicalUsers.map(user => user.username).sort()).toEqual(['AMY', 'bryan', 'chris', 'dan']);
    expect(getCanonicalUser('amy')?.username).toBe('AMY');
    expect(getCanonicalUser('unknown')).toBeUndefined();
  });

  it('keeps accounts with matching display names but distinct usernames and emails separate', () => {
    const users = [
      { username: 'jdoe', email: 'jdoe@example.com', name: 'J. Doe' },
      { username: 'janedoe', email: 'janedoe@example.com', name: 'J. Doe' }
    ];

    expect(groupUserIdentities(users).canonicalUsers).toEqual(users);
  });
});
