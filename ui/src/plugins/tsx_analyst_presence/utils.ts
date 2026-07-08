import type { UserStatus } from 'api/status';
import type { TagCategory, UserTags } from 'api/tags';
import type { AnalystStatusFilter } from './context/AnalystPresenceFiltersContext';

export type AnalystUser = UserStatus & {
  totalTagsCount: number;
};

export const enrichUserStatusResponse = (users: UserStatus[]): AnalystUser[] => {
  return users.map(user => ({
    ...user,
    totalTagsCount: Object.values(user.tags || {}).reduce((sum, arr) => sum + arr.length, 0)
  }));
};

export const sortUsersByStatus = (users: AnalystUser[]): AnalystUser[] => {
  return [...users].sort((a, b) => {
    if (a.status === null && b.status !== null) return 1; // a is unavailable, b is available
    if (a.status !== null && b.status === null) return -1; // a is available, b is unavailable
    if (a.status === null && b.status === null) return 0; // both are unavailable
    return Number(a.status) - Number(b.status); // both are available, sort by status number
  });
};

export const filterByKeyword = (users: AnalystUser[], keyword: string): AnalystUser[] => {
  const normalizedKeyword = keyword.trim().toLowerCase();

  if (!normalizedKeyword) {
    return users;
  }

  return users.filter(user => {
    const lowercaseName = user.name.toLowerCase();
    return lowercaseName.includes(normalizedKeyword);
  });
};

export const filterByStatus = (users: AnalystUser[], statusFilter: AnalystStatusFilter): AnalystUser[] => {
  if (statusFilter === 'all') {
    return users;
  }

  return users.filter(user => {
    if (statusFilter === 'available') {
      return user.status !== null;
    } else {
      return user.status === null;
    }
  });
};

export const filterByTags = (users: AnalystUser[], tagFilters: UserTags): AnalystUser[] => {
  const result: AnalystUser[] = [];

  users.forEach(user => {
    let matches = true;

    for (const category in tagFilters) {
      const tags = tagFilters[category as TagCategory];
      if (tags.length === 0) {
        continue; // No tags filters for this category, skip
      }

      const userTags = user.tags?.[category as TagCategory] || [];
      if (tags.some(tag => userTags.includes(tag))) {
        continue; // User has at least one match, check next category
      } else {
        matches = false; // No match for this category, exclude user
        break;
      }
    }

    if (matches) {
      result.push(user);
    }
  });

  return result;
};
