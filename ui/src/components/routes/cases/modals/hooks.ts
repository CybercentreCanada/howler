import type { Case } from 'models/entities/generated/Case';
import type { Event } from 'models/entities/generated/Event';
import type { Hit } from 'models/entities/generated/Hit';
import { useCallback, useMemo, useState } from 'react';
import type { RecordEntry } from './types';

export const defaultTitle = (record: Hit | Event): string => {
  if (record.__index === 'hit') {
    return `${record.howler.analytic} (${record.howler.id})`;
  }
  return `Event (${record.howler.id})`;
};

export const useFolderOptions = (selectedCase: Case | null): string[] => {
  return useMemo(() => {
    if (!selectedCase?.items) {
      return [];
    }

    const paths = new Set<string>();

    for (const item of selectedCase.items) {
      if (!item.path) {
        continue;
      }

      const parts = item.path.split('/');
      parts.pop();

      for (let i = 1; i <= parts.length; i++) {
        paths.add(parts.slice(0, i).join('/'));
      }
    }

    return Array.from(paths);
  }, [selectedCase]);
};

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export const useRecordEntries = (records: (Hit | Event)[]) => {
  const [entries, setEntries] = useState<RecordEntry[]>(() =>
    (records ?? []).map(record => ({
      record,
      path: '',
      title: defaultTitle(record)
    }))
  );

  const updateEntry = useCallback((index: number, field: 'title' | 'path', value: string) => {
    setEntries(prev => {
      const next = [...prev];
      next[index] = { ...next[index], [field]: value };
      return next;
    });
  }, []);

  return [entries, updateEntry] as const;
};
