import type { TagCategory } from 'api/tags';
import { useFetchTagsDictionary } from 'plugins/tsx_hooks/user_tags/useFetchTagsDictionary';
import { useCallback, useMemo, useState } from 'react';
import { AnalystPresenceFiltersContext, type AnalystPresenceFiltersContextType } from './AnalystPresenceFiltersContext';

export const AnalystPresenceFiltersProvider = ({ children }: { children: React.ReactNode }) => {
  const [activeStatusFilter, setActiveStatusFilter] =
    useState<AnalystPresenceFiltersContextType['activeStatusFilter']>('available');
  const [activeTagFilters, setActiveTagFilters] = useState<AnalystPresenceFiltersContextType['activeTagFilters']>({
    portfolio: [],
    products: [],
    primary_disciplines: []
  });

  const { data: tagsDictionary } = useFetchTagsDictionary();

  const tagsOptions = useMemo<Record<string, string>>(() => {
    if (!tagsDictionary) {
      return {};
    }

    return Object.values(tagsDictionary).reduce<Record<string, string>>((acc, entries) => {
      entries.forEach(entry => {
        acc[entry.value] = entry.name;
      });
      return acc;
    }, {});
  }, [tagsDictionary]);

  const handleSetStatusFilter = useCallback((status: AnalystPresenceFiltersContextType['activeStatusFilter']) => {
    setActiveStatusFilter(status);
  }, []);

  const handleSetTagFilters = useCallback((category: TagCategory, values: string[]) => {
    setActiveTagFilters(prev => ({ ...prev, [category]: values }));
  }, []);

  const handleToggleTagFilter = useCallback((category: TagCategory, value: string) => {
    setActiveTagFilters(prev => {
      const categoryTags = prev[category];
      const updatedCategoryTags = categoryTags.includes(value)
        ? categoryTags.filter(v => v !== value)
        : [...categoryTags, value];
      return { ...prev, [category]: updatedCategoryTags };
    });
  }, []);

  const contextValue = useMemo(
    () => ({
      activeStatusFilter,
      activeTagFilters,
      tagsDictionary,
      tagsOptions,
      setStatusFilter: handleSetStatusFilter,
      setTagFilters: handleSetTagFilters,
      toggleTagFilter: handleToggleTagFilter
    }),
    [
      activeStatusFilter,
      activeTagFilters,
      tagsDictionary,
      tagsOptions,
      handleSetStatusFilter,
      handleSetTagFilters,
      handleToggleTagFilter
    ]
  );

  return (
    <AnalystPresenceFiltersContext.Provider value={contextValue}>{children}</AnalystPresenceFiltersContext.Provider>
  );
};
