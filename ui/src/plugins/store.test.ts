/// <reference types="vitest" />
import { describe, expect, it, vi } from 'vitest';

const mockInstall = vi.hoisted(() => vi.fn());

vi.mock('react-pluggable', () => ({
  Event: class {
    constructor(public type: string) {}
  },
  createPluginStore: () => ({ install: mockInstall })
}));

describe('plugins/store', () => {
  it('tracks plugin registration and menu extensions', async () => {
    vi.resetModules();
    const { default: store } = await import('./store');

    const plugin = {
      name: 'demo',
      author: 'copilot',
      getPluginName: () => 'demo@1.0.0'
    } as any;

    store.install(plugin);
    store.install(plugin);
    expect(store.plugins).toEqual(['demo']);
    expect(mockInstall).toHaveBeenCalledTimes(1);

    expect(store.addLead('markdown')).toBe(true);
    expect(store.addLead('markdown')).toBe(false);
    expect(store.addPivot('pivot')).toBe(true);
    expect(store.addPivot('pivot')).toBe(false);
    expect(store.addOperation('triage')).toBe(true);
    expect(store.addOperation('triage')).toBe(false);

    store.addUserMenuItem({ i18nKey: 'user.profile', route: '/profile', icon: {} as any });
    store.addAdminMenuItem({ i18nKey: 'admin.users', route: '/admin', icon: {} as any });
    store.addMainMenuOperation({ type: 'append', parentId: 'root', item: { id: 'demo' } as any });
    store.addRoute({ path: 'custom', element: {} as any, children: [] });

    expect(store.leadFormats).toEqual(['markdown']);
    expect(store.pivotFormats).toEqual(['pivot']);
    expect(store.operations).toEqual(['triage']);
    expect(store.userMenuItems).toHaveLength(1);
    expect(store.adminMenuItems).toHaveLength(1);
    expect(store.routes).toHaveLength(1);

    const ops = store.mainMenuOperations as any[];
    expect(ops).toEqual([{ type: 'append', parentId: 'root', item: { id: 'demo' } }]);
    ops.push({ type: 'remove', targetId: 'root' });
    expect(store.mainMenuOperations).toHaveLength(1);
  });

  it('stores hit data on emitted hit events', async () => {
    vi.resetModules();
    const { HitEvent } = await import('./store');
    const event = new HitEvent('hit.opened', { id: 'abc123' } as any);

    expect(event.type).toBe('hit.opened');
    expect(event.hit).toEqual({ id: 'abc123' });
  });
});
