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

    it('renders chips labelled from item name/value for each seenIn id', () => {
      const _case = createMockCase({
        items: [
          { id: 'i1', type: 'hit', value: 'hit-001', name: 'first-hit' },
          { id: 'i2', type: 'event', value: 'obs-002', name: 'obs-two' },
          { id: 'i3', type: 'hit', value: 'hit-003', name: 'third-hit' }
        ]
      });
      render(
        <MemoryRouter>
          <Observable observable={makeObservable({ seenIn: ['hit-001', 'obs-002', 'hit-003'] })} case={_case} />
        </MemoryRouter>
      );
      expect(screen.getByText('first-hit')).toBeTruthy();
      expect(screen.getByText('obs-two')).toBeTruthy();
      expect(screen.getByText('third-hit')).toBeTruthy();
    });

    it('links each chip to /cases/:case_id/:item_path', () => {
      const _case = createMockCase({
        case_id: 'case-abc',
        items: [{ id: 'item-1', type: 'hit', value: 'hit-001', name: 'first-hit' }]
      });
      render(
        <MemoryRouter>
          <Observable observable={makeObservable({ seenIn: ['hit-001'] })} case={_case} />
        </MemoryRouter>
      );
      const link = screen.getByText('first-hit').closest('a');
      expect(link).not.toBeNull();
      expect(link?.getAttribute('href')).toBe('/cases/case-abc/first-hit');
    });
  });
});
