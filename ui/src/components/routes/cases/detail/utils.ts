import { has } from 'lodash-es';
import type { Case } from 'models/entities/generated/Case';
import type { Event } from 'models/entities/generated/Event';
import type { Hit } from 'models/entities/generated/Hit';
import type { Related } from 'models/entities/generated/Related';
import { buildPathFromID } from '../utils';
import type { ObservableEntry, ObservableRole, ObservableSource, ObservableType } from './types';

/** All Related fields that carry asset values */
export const OBSERVABLE_FIELDS: ObservableType[] = ['hash', 'hosts', 'ip', 'user', 'ids', 'id', 'uri', 'signature'];

/** Extract (type, value, seenInId) triples from a record's related field */
export const extractObservables = (related: Related | undefined): { type: ObservableType; value: string }[] => {
  if (!related) {
    return [];
  }

  const results: { type: ObservableType; value: string }[] = [];
  for (const field of OBSERVABLE_FIELDS) {
    const raw = related[field];
    if (!raw) {
      continue;
    }

    const values = Array.isArray(raw) ? raw : [raw];
    for (const value of values) {
      if (value) {
        results.push({ type: field, value: String(value) });
      }
    }
  }

  return results;
};

/** Deduplicate observables and resolve their record IDs to case-item sources */
export const buildObservableEntries = (_case: Case, records: (Hit | Event)[]): ObservableEntry[] => {
  const map: Record<string, ObservableEntry> = {};

  for (const record of records) {
    const related = (record as Hit).related ?? (record as Event).related;
    const recordId = (record as Hit).howler?.id ?? (record as Event).howler?.id;
    if (!recordId) {
      continue;
    }

    for (const { type, value } of extractObservables(related)) {
      const key = `${type}:${value}`;
      if (!has(map, key)) {
        map[key] = { type, value, sources: [], role: classifyRole(value, _case, records) };
      }

      const entry = map[key]!;
      if (entry.sources.some(existingSource => existingSource.id === recordId)) {
        continue;
      }

      const source = resolveSource(record, _case);
      if (!source) {
        continue;
      }

      entry.sources.push(source);
    }
  }

  return Object.values(map).filter(Boolean);
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

/** Resolve source metadata for an observable's record IDs */
export const resolveSource = (record: Hit | Event, _case: Case): ObservableSource => {
  if (!_case?.items?.length) {
    return null;
  }

  const item = _case.items.find(i => i.value === record.howler.id);
  if (!item) {
    return null;
  }

  return {
    id: record.howler.id,
    type: item.type as ObservableSource['type'],
    path: item.id ? buildPathFromID(_case, item.id) : undefined,
    label: item.name ?? item.value,
    escalation: record.howler.escalation
  };
};
