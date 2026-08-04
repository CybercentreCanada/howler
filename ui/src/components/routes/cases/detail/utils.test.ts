import type { Hit } from 'models/entities/generated/Hit';
import { createMockCase, createMockEvent, createMockHit } from 'tests/utils';
import { describe, expect, it } from 'vitest';
import { buildObservableEntries, classifyRole } from './utils';

// ---------------------------------------------------------------------------
// Pure logic tests — no React needed
// ---------------------------------------------------------------------------

describe('buildObservableEntries', () => {
  it('returns an empty array for records with no related field', () => {
    expect(buildObservableEntries(createMockCase(), [createMockHit({ howler: { id: 'h1' } })])).toEqual([]);
  });

  it('extracts a single IP with a resolved source', () => {
    const _case = createMockCase({
      items: [{ id: 'hit-item', type: 'hit', value: 'h1', name: 'First hit' }]
    });
    const result = buildObservableEntries(_case, [
      createMockHit({ howler: { id: 'h1', escalation: 'evidence' }, related: { ip: ['1.2.3.4'] } })
    ]);
    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({
      type: 'ip',
      value: '1.2.3.4',
      role: 'indicator',
      sources: [{ id: 'h1', type: 'hit', path: 'First hit', label: 'First hit', escalation: 'evidence' }]
    });
  });

  it('extracts multiple fields from a single record', () => {
    const result = buildObservableEntries(createMockCase(), [
      createMockHit({ howler: { id: 'h1' }, related: { ip: ['1.2.3.4'], user: ['alice'] } })
    ]);
    const types = result.map(a => a.type).sort();
    expect(types).toEqual(['ip', 'user']);
  });

  it('deduplicates the same observable value across multiple records', () => {
    const _case = createMockCase({
      items: [
        { id: 'hit-item', type: 'hit', value: 'h1', name: 'First hit' },
        { id: 'event-item', type: 'event', value: 'obs1', name: 'First event' }
      ]
    });
    const result = buildObservableEntries(_case, [
      createMockHit({ howler: { id: 'h1' }, related: { ip: ['1.2.3.4'] } }),
      createMockEvent({ howler: { id: 'obs1' }, related: { ip: ['1.2.3.4'] } })
    ]);
    expect(result).toHaveLength(1);
    expect(result[0].sources).toEqual([
      { id: 'h1', type: 'hit', path: 'First hit', label: 'First hit', escalation: undefined },
      { id: 'obs1', type: 'event', path: 'First event', label: 'First event', escalation: undefined }
    ]);
  });

  it('keeps distinct observable values as separate entries', () => {
    const result = buildObservableEntries(createMockCase(), [
      createMockHit({ howler: { id: 'h1' }, related: { ip: ['1.2.3.4'] } }),
      createMockHit({ howler: { id: 'h2' }, related: { ip: ['5.6.7.8'] } })
    ]);
    expect(result).toHaveLength(2);
  });

  it('does not duplicate sources when the same record appears twice for the same observable', () => {
    const _case = createMockCase({ items: [{ id: 'hit-item', type: 'hit', value: 'h1' }] });
    const result = buildObservableEntries(_case, [
      createMockHit({ howler: { id: 'h1' }, related: { ip: ['1.2.3.4'] } }),
      createMockHit({ howler: { id: 'h1' }, related: { ip: ['1.2.3.4'] } })
    ]);
    expect(result[0].sources).toEqual([{ id: 'h1', type: 'hit', path: 'h1', label: 'h1', escalation: undefined }]);
  });

  it('skips records with no howler.id', () => {
    const noId: Hit = { related: { ip: ['1.2.3.4'] } } as any;
    expect(buildObservableEntries(createMockCase(), [noId])).toEqual([]);
  });

  it('handles the scalar `id` field on Related', () => {
    const result = buildObservableEntries(createMockCase(), [
      createMockHit({ howler: { id: 'h1' }, related: { id: 'some-id' } })
    ]);
    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({ type: 'id', value: 'some-id', role: 'indicator', sources: [] });
  });

  it('handles array fields like hash, hosts, user, ids, uri, signature', () => {
    const related = {
      hash: ['abc123'],
      hosts: ['host.example.com'],
      user: ['bob'],
      ids: ['guid-1'],
      uri: ['https://example.com'],
      signature: ['rule-X']
    };
    const result = buildObservableEntries(createMockCase(), [createMockHit({ howler: { id: 'h1' }, related })]);
    const types = result.map(a => a.type).sort();
    expect(types).toEqual(['hash', 'hosts', 'ids', 'signature', 'uri', 'user']);
  });
});

// ---------------------------------------------------------------------------
// classifyRole tests
// ---------------------------------------------------------------------------

describe('classifyRole', () => {
  const emptyCase = createMockCase();

  it('returns "threat" when value is in case.threats', () => {
    const _case = createMockCase({ threats: ['malicious.exe'] });
    const records = [createMockHit({ howler: { id: 'h1' } })];
    expect(classifyRole('malicious.exe', _case, records)).toBe('threat');
  });

  it('returns "target" when value is in case.targets', () => {
    const _case = createMockCase({ targets: ['server-01'] });
    const records = [createMockHit({ howler: { id: 'h1' } })];
    expect(classifyRole('server-01', _case, records)).toBe('target');
  });

  it('returns "indicator" when value is in case.indicators', () => {
    const _case = createMockCase({ indicators: ['1.2.3.4'] });
    const records = [createMockHit({ howler: { id: 'h1' } })];
    expect(classifyRole('1.2.3.4', _case, records)).toBe('indicator');
  });

  it('returns "threat" when value matches howler.outline.threat', () => {
    const records = [createMockHit({ howler: { id: 'h1', outline: { threat: 'malicious.exe' } } })];
    expect(classifyRole('malicious.exe', emptyCase, records)).toBe('threat');
  });

  it('returns "threat" with case-insensitive matching', () => {
    const records = [createMockHit({ howler: { id: 'h1', outline: { threat: 'Malicious.EXE' } } })];
    expect(classifyRole('malicious.exe', emptyCase, records)).toBe('threat');
  });

  it('does not match threat by substring — only exact match', () => {
    const records = [createMockHit({ howler: { id: 'h1', outline: { threat: 'evil.com dropped payload' } } })];
    // No substring match, defaults to indicator
    expect(classifyRole('evil.com', emptyCase, records)).toBe('indicator');
  });

  it('classifies as indicator when value is in outline.indicators but not in threat/target', () => {
    const records = [
      createMockHit({
        howler: { id: 'h1', outline: { threat: 'actor-x', target: 'server-01', indicators: ['1.2.3.4'] } }
      })
    ];
    expect(classifyRole('1.2.3.4', emptyCase, records)).toBe('indicator');
  });

  it('returns "target" when value matches howler.outline.target', () => {
    const records = [createMockHit({ howler: { id: 'h1', outline: { target: 'server-01' } } })];
    expect(classifyRole('server-01', emptyCase, records)).toBe('target');
  });

  it('returns "indicator" when value matches threat.indicator.ip', () => {
    const records = [
      createMockHit({
        howler: { id: 'h1' },
        threat: { indicator: { ip: '10.0.0.1' } }
      })
    ];
    expect(classifyRole('10.0.0.1', emptyCase, records)).toBe('indicator');
  });

  it('returns "indicator" when value matches threat.indicator.description', () => {
    const records = [
      createMockHit({
        howler: { id: 'h1' },
        threat: { indicator: { description: 'suspicious-hash-abc123' } }
      })
    ];
    expect(classifyRole('suspicious-hash-abc123', emptyCase, records)).toBe('indicator');
  });

  it('defaults to "indicator" when value has no specific classification', () => {
    const records = [createMockHit({ howler: { id: 'h1' }, related: { ip: ['5.6.7.8'] } })];
    expect(classifyRole('5.6.7.8', emptyCase, records)).toBe('indicator');
  });

  it('case-level threats take priority over per-record outline.target', () => {
    const _case = createMockCase({ threats: ['dual-use.exe'] });
    const records = [createMockHit({ howler: { id: 'h1', outline: { target: 'dual-use.exe' } } })];
    expect(classifyRole('dual-use.exe', _case, records)).toBe('threat');
  });

  it('trims whitespace before comparing', () => {
    const records = [createMockHit({ howler: { id: 'h1', outline: { threat: '  evil.com  ' } } })];
    expect(classifyRole('evil.com', emptyCase, records)).toBe('threat');
  });
});
