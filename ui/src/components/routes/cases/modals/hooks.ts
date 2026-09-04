import type { Case } from 'models/entities/generated/Case';
import type { Event } from 'models/entities/generated/Event';
import type { Hit } from 'models/entities/generated/Hit';
import { useCallback, useMemo, useState } from 'react';
import { buildPathFromID } from '../utils';
import type { FolderOption, RecordEntry } from './types';

export const defaultTitle = (record: Hit | Event): string => {
  if (record.__index === 'hit') {
    return `${record.howler.analytic} (${record.howler.id})`;
  }
  return `Event (${record.howler.id})`;
};

export const useFolderOptions = (selectedCase: Case | null): FolderOption[] => {
  return useMemo(() => {
    if (!selectedCase?.items) {
      return [];
    }

    const options: FolderOption[] = [];
    for (const item of selectedCase.items) {
      if (item.type === 'folder' && item.id) {
        options.push({ id: item.id, label: buildPathFromID(selectedCase, item.id) });
      }
    }

    return options;
  }, [selectedCase]);
};

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export const useRecordEntries = (records: (Hit | Event)[]) => {
  const [entries, setEntries] = useState<RecordEntry[]>(() =>
    (records ?? []).map((record): RecordEntry => ({
      record,
      parent: null,
      name: defaultTitle(record)
    }))
  );

  const updateEntry = useCallback((index: number, field: 'name' | 'parent', value: string | null) => {
    setEntries(prev => {
      const next = [...prev];
      next[index] = { ...next[index], [field]: value };
      return next;
    });
  }, []);

  return [entries, updateEntry] as const;
};
