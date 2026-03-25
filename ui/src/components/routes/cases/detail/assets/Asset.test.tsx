/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { createMockCase } from 'tests/utils';
import { describe, expect, it } from 'vitest';
import Asset, { type AssetEntry } from './Asset';

const makeAsset = (overrides: Partial<AssetEntry> = {}): AssetEntry => ({
  type: 'ip',
  value: '192.168.1.1',
  seenIn: [],
  ...overrides
});

describe('Asset', () => {
  describe('type chip', () => {
    it('renders the correct label for each type', () => {
      const cases: AssetEntry['type'][] = ['hash', 'hosts', 'ip', 'user', 'ids', 'id', 'uri', 'signature'];
      for (const type of cases) {
        const { unmount } = render(
          <MemoryRouter>
            <Asset asset={makeAsset({ type, value: 'x' })} case={createMockCase()} />
          </MemoryRouter>
        );
        expect(screen.getByText(`page.cases.assets.type.${type}`)).toBeTruthy();
        unmount();
      }
    });
  });

  describe('value display', () => {
    it('renders the asset value', () => {
      render(
        <MemoryRouter>
          <Asset asset={makeAsset({ value: '10.0.0.1' })} case={createMockCase()} />
        </MemoryRouter>
      );
      expect(screen.getByText('10.0.0.1')).toBeTruthy();
    });

    it('renders long hash values without truncation', () => {
      const hash = 'a'.repeat(64);
      render(
        <MemoryRouter>
          <Asset asset={makeAsset({ type: 'hash', value: hash })} case={createMockCase()} />
        </MemoryRouter>
      );
      expect(screen.getByText(hash)).toBeTruthy();
    });
  });

  describe('seen-in chips', () => {
    it('renders nothing when seenIn is empty', () => {
      render(
        <MemoryRouter>
          <Asset asset={makeAsset({ seenIn: [] })} case={createMockCase()} />
        </MemoryRouter>
      );
      expect(screen.queryByText('page.cases.assets.seen_in')).toBeNull();
    });

    it('renders "Seen in" label when seenIn has entries', () => {
      const _case = createMockCase({
        items: [{ id: 'hit-001', path: 'alerts/test-analytic (hit-001)', type: 'hit', value: 'hit-001' }]
      });
      render(
        <MemoryRouter>
          <Asset asset={makeAsset({ seenIn: ['hit-001'] })} case={_case} />
        </MemoryRouter>
      );
      expect(screen.getByText('page.cases.assets.seen_in')).toBeTruthy();
    });

    it('renders a chip labelled with entry.path for each seenIn id', () => {
      const _case = createMockCase({
        items: [
          { id: 'hit-001', path: 'alerts/my-analytic (hit-001)', type: 'hit', value: 'hit-001' },
          { id: 'obs-002', path: 'observables/obs-002', type: 'observable', value: 'obs-002' },
          { id: 'hit-003', path: 'alerts/other-analytic (hit-003)', type: 'hit', value: 'hit-003' }
        ]
      });
      render(
        <MemoryRouter>
          <Asset asset={makeAsset({ seenIn: ['hit-001', 'obs-002', 'hit-003'] })} case={_case} />
        </MemoryRouter>
      );
      expect(screen.getByText('alerts/my-analytic (hit-001)')).toBeTruthy();
      expect(screen.getByText('observables/obs-002')).toBeTruthy();
      expect(screen.getByText('alerts/other-analytic (hit-003)')).toBeTruthy();
    });

    it('links each chip to /cases/:case_id/:path', () => {
      const _case = createMockCase({
        case_id: 'case-abc',
        items: [{ id: 'hit-001', path: 'alerts/my-analytic (hit-001)', type: 'hit', value: 'hit-001' }]
      });
      render(
        <MemoryRouter>
          <Asset asset={makeAsset({ seenIn: ['hit-001'] })} case={_case} />
        </MemoryRouter>
      );
      const link = screen.getByText('alerts/my-analytic (hit-001)').closest('a');
      expect(link).not.toBeNull();
      expect(link?.getAttribute('href')).toBe('/cases/case-abc/alerts/my-analytic (hit-001)');
    });
  });
});
