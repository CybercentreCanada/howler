import type { TagCategory, TagsDictionary } from 'api/tags';
import { createContext } from 'react';

export type AnalystStatusFilter = 'available' | 'unavailable' | 'all';

export type AnalystPresenceFiltersContextType = {
  activeStatusFilter: AnalystStatusFilter;
  activeTagFilters: Record<TagCategory, string[]>;
  tagsDictionary: TagsDictionary | undefined;
  tagsOptions: Record<string, string>;
  setStatusFilter: (status: AnalystStatusFilter) => void;
  setTagFilters: (category: TagCategory, values: string[]) => void;
  toggleTagFilter: (category: TagCategory, value: string) => void;
};

export const AnalystPresenceFiltersContext = createContext<AnalystPresenceFiltersContextType | null>(null);
