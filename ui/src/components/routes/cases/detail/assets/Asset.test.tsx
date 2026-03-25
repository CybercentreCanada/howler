/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
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
      const cases: [AssetEntry['type'], string][] = [
        ['hash', 'Hash'],
        ['hosts', 'Host'],
        ['ip', 'IP'],
        ['user', 'User'],
        ['ids', 'ID'],
        ['id', 'ID'],
        ['uri', 'URI'],
        ['signature', 'Signature']
      ];
      for (const [type, label] of cases) {
        const { unmount } = render(<Asset asset={makeAsset({ type, value: 'x' })} />);
        expect(screen.getByText(label)).toBeTruthy();
        unmount();
      }
    });
  });

  describe('value display', () => {
    it('renders the asset value', () => {
      render(<Asset asset={makeAsset({ value: '10.0.0.1' })} />);
      expect(screen.getByText('10.0.0.1')).toBeTruthy();
    });

    it('renders long hash values without truncation', () => {
      const hash = 'a'.repeat(64);
      render(<Asset asset={makeAsset({ type: 'hash', value: hash })} />);
      expect(screen.getByText(hash)).toBeTruthy();
    });
  });

  describe('seen-in chips', () => {
    it('renders nothing when seenIn is empty', () => {
      render(<Asset asset={makeAsset({ seenIn: [] })} />);
      expect(screen.queryByText('Seen in')).toBeNull();
    });

    it('renders "Seen in" label when seenIn has entries', () => {
      render(<Asset asset={makeAsset({ seenIn: ['hit-001'] })} />);
      expect(screen.getByText('Seen in')).toBeTruthy();
    });

    it('renders a chip for each seenIn id', () => {
      render(<Asset asset={makeAsset({ seenIn: ['hit-001', 'obs-002', 'hit-003'] })} />);
      expect(screen.getByText('hit-001')).toBeTruthy();
      expect(screen.getByText('obs-002')).toBeTruthy();
      expect(screen.getByText('hit-003')).toBeTruthy();
    });
  });
});
