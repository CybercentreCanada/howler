import type { Case } from 'models/entities/generated/Case';
import type { Event } from 'models/entities/generated/Event';
import type { Hit } from 'models/entities/generated/Hit';
import type { Related } from 'models/entities/generated/Related';
import { type ObservableEntry, type ObservableRole, type ObservableSource, type ObservableType } from './types';

/** All Related fields that carry asset values */
export const OBSERVABLE_FIELDS: ObservableType[] = ['hash', 'hosts', 'ip', 'user', 'ids', 'id', 'uri', 'signature'];

/** Extract (type, value, seenInId) triples from a record's related field */
export const extractObservables = (
  related: Related | undefined,
  recordId: string
): { type: ObservableType; value: string; id: string }[] => {
  if (!related) {
    return [];
  }

  const results: { type: ObservableType; value: string; id: string }[] = [];
  for (const field of OBSERVABLE_FIELDS) {
    const raw = related[field];
    if (!raw) {
      continue;
    }

    const values = Array.isArray(raw) ? raw : [raw];
    for (const value of values) {
      if (value) {
        results.push({ type: field, value: String(value), id: recordId });
      }
    }
  }

  return results;
};

/** Deduplicate and merge seenIn lists into a map keyed by `type:value` */
export const buildObservableEntries = (records: Partial<Hit | Event>[]): ObservableEntry[] => {
  const map = new Map<string, ObservableEntry>();

  for (const record of records) {
    const related = (record as Hit).related ?? (record as Event).related;
    const recordId = (record as Hit).howler?.id ?? (record as Event).howler?.id;
    if (!recordId) {
      continue;
    }

    for (const { type, value, id } of extractObservables(related, recordId)) {
      const key = `${type}:${value}`;
      if (!map.has(key)) {
        map.set(key, { type, value, seenIn: [] });
      }

      const entry = map.get(key)!;
      if (!entry.seenIn.includes(id)) {
        entry.seenIn.push(id);
      }
    }
  }

  return Array.from(map.values());
};

/**
 * Classify an asset's role based on case-level lists and per-record outline fields.
 *
 * Resolution order:
 * 1. Case-level `threats[]`, `targets[]`, `indicators[]` (authoritative).
 * 2. Per-record `outline.threat` / `outline.target` (exact match).
 * 3. Per-record `outline.indicators[]`, `threat.indicator.ip/.description`.
 * 4. Default: "indicator" — all assets come from `related.*` fields which are IOCs by nature.
 *
 * Comparison is case-insensitive and trimmed.
 */
export const classifyRole = (value: string, _case: Case, records: Partial<Hit | Event>[]): ObservableRole => {
  const normalized = value.trim().toLowerCase();

  // Case-level classification (most authoritative)
  if (_case.threats?.some(t => String(t).trim().toLowerCase() === normalized)) {
    return 'threat';
  }

  if (_case.targets?.some(t => String(t).trim().toLowerCase() === normalized)) {
    return 'target';
  }

  if (_case.indicators?.some(i => String(i).trim().toLowerCase() === normalized)) {
    return 'indicator';
  }

  // Per-record outline checks
  for (const record of records) {
    const howlerOutline = record.howler?.outline;
    if (howlerOutline) {
      if (howlerOutline.threat && howlerOutline.threat.trim().toLowerCase() === normalized) {
        return 'threat';
      }

      if (howlerOutline.target && howlerOutline.target.trim().toLowerCase() === normalized) {
        return 'target';
      }

      if (howlerOutline.indicators?.some(ind => ind.trim().toLowerCase() === normalized)) {
        return 'indicator';
      }
    }

    const indicator = record.threat?.indicator;
    if (indicator) {
      const indicatorIp = indicator.ip?.trim().toLowerCase();
      const indicatorDesc = indicator.description?.trim().toLowerCase();
      if ((indicatorIp && indicatorIp === normalized) || (indicatorDesc && indicatorDesc === normalized)) {
        return 'indicator';
      }
    }
  }

  // Default: assets from related.* are IOCs
  return 'indicator';
};

/** Resolve source metadata for an asset's seenIn IDs */
export const resolveSources = (
  seenIn: string[],
  caseItems: Case['items'],
  escalationMap: Map<string, string>
): ObservableSource[] => {
  if (!caseItems?.length) {
    return [];
  }

  return seenIn
    .map(id => {
      const item = caseItems.find(i => i.value === id);
      if (!item) {
        return null;
      }

      return {
        id,
        type: item.type as 'hit' | 'event' | 'case',
        path: item.path,
        escalation: escalationMap.get(id)
      };
    })
    .filter(Boolean) as ObservableSource[];
};
