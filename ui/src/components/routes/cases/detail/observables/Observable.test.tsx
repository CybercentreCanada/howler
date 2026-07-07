/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { createMockCase } from 'tests/utils';
import { describe, expect, it } from 'vitest';
import type { ObservableEntry } from '../types';
import Observable from './Observable';

const makeObservable = (overrides: Partial<ObservableEntry> = {}): ObservableEntry => ({
  type: 'ip',
  value: '192.168.1.1',
  seenIn: [],
  ...overrides
});

describe('Observable', () => {
  describe('type chip', () => {
    it('renders the correct label for each type', () => {
      const cases: ObservableEntry['type'][] = ['hash', 'hosts', 'ip', 'user', 'ids', 'id', 'uri', 'signature'];
      for (const type of cases) {
        const { unmount } = render(
          <MemoryRouter>
            <Observable observable={makeObservable({ type, value: 'x' })} case={createMockCase()} />
          </MemoryRouter>
        );
        expect(screen.getByText(`page.cases.observables.type.${type}`)).toBeTruthy();
        unmount();
      }
    });
  });

  describe('value display', () => {
    it('renders the asset value', () => {
      render(
        <MemoryRouter>
          <Observable observable={makeObservable({ value: '10.0.0.1' })} case={createMockCase()} />
        </MemoryRouter>
      );
      expect(screen.getByText('10.0.0.1')).toBeTruthy();
    });

    it('renders long hash values without truncation', () => {
      const hash = 'a'.repeat(64);
      render(
        <MemoryRouter>
          <Observable observable={makeObservable({ type: 'hash', value: hash })} case={createMockCase()} />
        </MemoryRouter>
      );
      expect(screen.getByText(hash)).toBeTruthy();
    });
  });

  describe('seen-in chips', () => {
    it('renders nothing when seenIn is empty', () => {
      render(
        <MemoryRouter>
          <Observable observable={makeObservable({ seenIn: [] })} case={createMockCase()} />
        </MemoryRouter>
      );
      expect(screen.queryByText('page.cases.observables.seen_in')).toBeNull();
    });

    it('renders "Seen in" label when seenIn has entries', () => {
      const _case = createMockCase({
        items: [{ type: 'hit', value: 'hit-001' }]
      });
      render(
        <MemoryRouter>
          <Observable observable={makeObservable({ seenIn: ['hit-001'] })} case={_case} />
        </MemoryRouter>
      );
      expect(screen.getByText('page.cases.observables.seen_in')).toBeTruthy();
    });

    it('renders a chip labelled with entry.path for each seenIn id', () => {
      const _case = createMockCase({
        items: [
          { type: 'hit', value: 'hit-001' },
          { type: 'event', value: 'obs-002' },
          { type: 'hit', value: 'hit-003' }
        ]
      });
      render(
        <MemoryRouter>
          <Observable observable={makeObservable({ seenIn: ['hit-001', 'obs-002', 'hit-003'] })} case={_case} />
        </MemoryRouter>
      );
      expect(screen.getByText('alerts/my-analytic (hit-001)')).toBeTruthy();
      expect(screen.getByText('events/obs-002')).toBeTruthy();
      expect(screen.getByText('alerts/other-analytic (hit-003)')).toBeTruthy();
    });

    it('links each chip to /cases/:case_id/:path', () => {
      const _case = createMockCase({
        case_id: 'case-abc',
        items: [{ type: 'hit', value: 'hit-001' }]
      });
      render(
        <MemoryRouter>
          <Observable observable={makeObservable({ seenIn: ['hit-001'] })} case={_case} />
        </MemoryRouter>
      );
      const link = screen.getByText('alerts/my-analytic (hit-001)').closest('a');
      expect(link).not.toBeNull();
      expect(link?.getAttribute('href')).toBe('/cases/case-abc/alerts/my-analytic (hit-001)');
    });
  });
});
